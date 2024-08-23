package cosignvalidator

import (
	"connaisseur/internal/constants"
	"connaisseur/internal/image"
	"connaisseur/internal/policy"
	"connaisseur/internal/utils"
	"connaisseur/internal/validator/auth"
	"context"
	"crypto/tls"
	"crypto/x509"
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"strings"

	"github.com/google/go-containerregistry/pkg/authn"
	"github.com/google/go-containerregistry/pkg/name"
	"github.com/google/go-containerregistry/pkg/v1/remote"
	"github.com/sigstore/cosign/v2/cmd/cosign/cli/fulcio"
	"github.com/sigstore/cosign/v2/cmd/cosign/cli/options"
	"github.com/sigstore/cosign/v2/cmd/cosign/cli/rekor"
	"github.com/sigstore/cosign/v2/cmd/cosign/cli/sign"
	"github.com/sigstore/cosign/v2/pkg/cosign"
	"github.com/sigstore/cosign/v2/pkg/oci"
	ociremote "github.com/sigstore/cosign/v2/pkg/oci/remote"
	"github.com/sigstore/rekor/pkg/generated/client"
	"github.com/sigstore/sigstore/pkg/tuf"
	"github.com/sirupsen/logrus"
)

type CosignValidator struct {
	// Name of the validator
	Name string `validate:"required"`
	// type of the validator (will always be "cosign")
	Type string `validate:"eq=cosign"`
	// client for connecting to the Rekor instance
	Rekor *client.Rekor
	// public key of the Rekor instance or nil if using the Sigstore one
	rekorPubkey *cosign.TrustedTransparencyLogPubKeys
	// certificate of the Fulcio instance or nil if using the Sigstore one
	fulcioCert *x509.CertPool
	// public key of the CT log or nil if using the Sigstore one
	ctLogPubkey *cosign.TrustedTransparencyLogPubKeys
	// self signed certificate of the registry
	Cert *x509.CertPool
	// authentication for the registry
	Auth auth.Auth
	// trust roots of the validator
	TrustRoots []auth.TrustRoot `validate:"min=1,dive"`
}

// only for unmashalling yaml
type CosignValidatorYaml struct {
	Name string `yaml:"name"`
	Type string `yaml:"type"`
	Host struct {
		Rekor       string `yaml:"rekor"`
		RekorPubkey string `yaml:"rekorPubkey"`
		FulcioCert  string `yaml:"fulcioCert"`
		CTLogPubkey string `yaml:"ctLogPubkey"`
	} `yaml:"host"`
	Cert       string           `yaml:"cert"`
	Auth       auth.Auth        `yaml:"auth"`
	TrustRoots []auth.TrustRoot `yaml:"trustRoots"`
}

// cosign payload structure, returned by cosign
// when verifying signatures
type CosignPayload struct {
	Critical CosignPayloadCritical `json:"critical"`
	Optional map[string]string
}

type CosignPayloadCritical struct {
	Identity CosignPayloadIdentity `json:"identity"`
	Image    CosignPayloadImage    `json:"image"`
	Type     string                `json:"type"`
}

type CosignPayloadIdentity struct {
	DockerReference string `json:"docker-reference"`
}

type CosignPayloadImage struct {
	Digest string `json:"Docker-manifest-digest"`
}

// verifierOutput is a struct to hold the output
// of internal the verifier goroutine
type verifierOutput struct {
	checkedSignatures   []oci.Signature
	err                 error
	propagationErr      error
	validatingTrustRoot string
}

// Unmarshals the yaml into a CosignValidator object, validating
// some attributes in the process
func (cv *CosignValidator) UnmarshalYAML(unmarshal func(interface{}) error) error {
	var valData CosignValidatorYaml
	if err := unmarshal(&valData); err != nil {
		return err
	}

	// if no rekor host is provided, use default
	if valData.Host.Rekor == "" {
		valData.Host.Rekor = constants.DefaultRekorHost
	}

	// create and validate rekor client
	rekorClient, err := rekor.NewClient(valData.Host.Rekor)
	if err != nil {
		return fmt.Errorf("unable to create Rekor client for %s: %s", valData.Host.Rekor, err)
	}

	// validate rekor pubkey
	var rekorPub *cosign.TrustedTransparencyLogPubKeys
	if valData.Host.RekorPubkey != "" {
		tempRekorPub := cosign.NewTrustedTransparencyLogPubKeys()
		err = tempRekorPub.AddTransparencyLogPubKey([]byte(valData.Host.RekorPubkey), tuf.Active)
		if err != nil {
			return fmt.Errorf("error adding rekor public key: %s", err)
		}
		rekorPub = &tempRekorPub
	}

	// validate trust roots
	if len(valData.TrustRoots) < 1 {
		return fmt.Errorf("no trust roots provided for validator %s", valData.Name)
	}

	// validate certificate
	var cert *x509.CertPool
	if valData.Cert != "" {
		cert = x509.NewCertPool()
		if !cert.AppendCertsFromPEM([]byte(valData.Cert)) {
			return fmt.Errorf("invalid certificate for validator %s", valData.Name)
		}
	}

	// validate fulcio certificate
	var fulcioCert *x509.CertPool
	if valData.Host.FulcioCert != "" {
		fulcioCert = x509.NewCertPool()
		if !fulcioCert.AppendCertsFromPEM([]byte(valData.Host.FulcioCert)) {
			return fmt.Errorf("invalid fulcio certificate for validator %s", valData.Name)
		}
	}

	// validate ct log public key
	var ctPub *cosign.TrustedTransparencyLogPubKeys
	if valData.Host.CTLogPubkey != "" {
		tempCTPub := cosign.NewTrustedTransparencyLogPubKeys()
		err := tempCTPub.AddTransparencyLogPubKey([]byte(valData.Host.CTLogPubkey), tuf.Active)
		if err != nil {
			return fmt.Errorf("error adding ct log public key: %s", err)
		}
		ctPub = &tempCTPub
	}

	cv.Name = valData.Name
	cv.Type = valData.Type
	cv.Rekor = rekorClient
	cv.rekorPubkey = rekorPub
	cv.fulcioCert = fulcioCert
	cv.ctLogPubkey = ctPub
	cv.Cert = cert
	cv.Auth = valData.Auth
	cv.TrustRoots = valData.TrustRoots
	return nil
}

// validates the given image against the given policy
// returns the digest of the image if validation was successful
// returns an error otherwise
func (cv *CosignValidator) ValidateImage(
	ctx context.Context,
	img *image.Image,
	args policy.RuleOptions,
) (string, error) {
	// transform image into right format
	imageRef, _ := sign.GetAttachedImageRef(img, "")

	// collect all trust root names needed for validation
	var trustRootReferences []string
	if args.TrustRoot == "*" && (args.Threshold > len(args.Required) || len(args.Required) == 0) {
		trustRootReferences = utils.Map[auth.TrustRoot, string](
			cv.TrustRoots,
			func(trustRoot auth.TrustRoot) string { return trustRoot.Name },
		)
	} else if args.TrustRoot == "*" && len(args.Required) > 0 {
		trustRootReferences = args.Required
	} else {
		trustRootReferences = []string{args.TrustRoot}
	}

	// set up cosign options
	opts, err := cv.setupOptions(ctx, args, img)
	if err != nil {
		return "", fmt.Errorf("error setting up cosign options: %s", err)
	}

	// load verifiers for trust roots
	verifiers, err := cv.verifiers(ctx, trustRootReferences)
	if err != nil {
		return "", fmt.Errorf("error getting verifiers: %s", err)
	}

	numberOfTrustRoots := len(trustRootReferences)
	verifierOutputChannel := make(chan verifierOutput, numberOfTrustRoots)

	// do cosign validation on image per trust root in parallel
	for _, verifier := range verifiers {
		// copy options since they are
		// modified in the goroutine
		copts := *opts
		go cv.validateWithVerifier(ctx, imageRef, copts, verifier, verifierOutputChannel)
	}

	validatingTrustRoots := []string{}
	checkedSignatures := []oci.Signature{}
	propagateErrors := []error{}
	for i := 0; i < numberOfTrustRoots; i++ {
		output := <-verifierOutputChannel
		if output.err != nil {
			return "", output.err
		}
		checkedSignatures = append(checkedSignatures, output.checkedSignatures...)
		validatingTrustRoots = append(validatingTrustRoots, output.validatingTrustRoot)
		if output.propagationErr != nil {
			propagateErrors = append(propagateErrors, output.propagationErr)
		}
	}

	var threshold int
	if args.TrustRoot == "*" && len(args.Required) == 0 && !(args.Threshold > 0) {
		threshold = len(verifiers)
	} else if args.TrustRoot == "*" && args.Threshold > 0 {
		threshold = args.Threshold
	}

	numberOfCheckedSignatures := len(checkedSignatures)
	// check threshold
	if threshold > 0 && numberOfCheckedSignatures < threshold {
		return "", fmt.Errorf(
			"validation threshold not reached (%d/%d)",
			numberOfCheckedSignatures,
			threshold,
		)
	}

	// check required signatures
	if len(args.Required) > 0 {
		logrus.Debugf("required signatures: %s", args.Required)
		// find missing required signatures
		missing := utils.SetSubstract(args.Required, validatingTrustRoots)
		if len(missing) != 0 {
			return "", fmt.Errorf("missing required signatures from %+v", missing)
		}
	}

	logrus.Debugf(
		"num signatures: %d/%d by validating trust root names: %+v",
		numberOfCheckedSignatures,
		numberOfTrustRoots,
		validatingTrustRoots,
	)

	// extract digests from validation
	digests := map[string]struct{}{}
	for _, signature := range checkedSignatures {
		var payload CosignPayload
		payloadBytes, err := signature.Payload()
		if err != nil {
			return "", err
		}

		err = json.Unmarshal(payloadBytes, &payload)
		if err != nil {
			return "", err
		}

		digests[payload.Critical.Image.Digest] = struct{}{}
	}

	// check all digests are the same
	if len(digests) > 1 {
		return "", fmt.Errorf("ambiguous digests")
	}

	for k := range digests {
		// return the only digest
		return k, nil
	}

	// propagate errors if no digests were found
	if len(propagateErrors) > 0 {
		return "", fmt.Errorf("error validating image: %s", propagateErrors)
	}

	// no signed digests
	return "", fmt.Errorf("no signed digests")
}

func (cv *CosignValidator) validateWithVerifier(
	ctx context.Context,
	imageRef name.Reference,
	opts cosign.CheckOpts,
	verifier Verifier,
	verifierOutputChannel chan<- verifierOutput,
) {
	if verifier.KeyVerifier != nil { // key verifier
		opts.SigVerifier = verifier.KeyVerifier
	} else { // keyless verifier
		root, intermediate, err := cv.getFulcioCerts()
		if err != nil {
			verifierOutputChannel <- verifierOutput{nil, err, nil, ""}
			return
		}
		opts.RootCerts = root
		opts.IntermediateCerts = intermediate
		opts.Identities = append(opts.Identities, verifier.KeylessVerifier)
	}

	logrus.Debugf("validating image %s with trust root %s", imageRef, verifier.Name)
	// do cosign validation on image
	validSignatures, _, err := cosign.VerifyImageSignatures(
		ctx,
		imageRef,
		&opts,
	)
	if err != nil {
		// short-circuit if the image doesn't exist
		if strings.HasPrefix(err.Error(), "image tag not found:") {
			msg := fmt.Sprintf("image %s does not exist: %s", imageRef, err)
			logrus.Info(msg)
			verifierOutputChannel <- verifierOutput{nil, errors.New(msg), nil, ""}
			return
		}
		logrus.Debugf("error verifying signatures with verifier for trust root %s: %s", verifier.Name, err)
		verifierOutputChannel <- verifierOutput{nil, nil, err, ""}
		return
	}
	verifierOutputChannel <- verifierOutput{validSignatures, nil, nil, verifier.Name}
}

// sets up the options for the Cosign validation, which includes
// turning the trust roots into verifiers, adding authentication
// and setting self-signed certificates
func (cv *CosignValidator) setupOptions(
	ctx context.Context,
	args policy.RuleOptions,
	img *image.Image,
) (*cosign.CheckOpts, error) {
	boolOrDefault := func(b *bool, default_ bool) bool {
		if b == nil {
			return default_
		}
		return *b
	}
	verifyTlog, verifySCT := boolOrDefault(args.VerifyTLog, true), boolOrDefault(args.VerifySCT, true)
	opts := &cosign.CheckOpts{IgnoreTlog: !verifyTlog, IgnoreSCT: !verifySCT}

	// set authentication
	auth := cv.Auth.LookUp(img.Context().String())
	registryOpts := options.RegistryOptions{
		AllowInsecure:      false,
		AllowHTTPRegistry:  false,
		KubernetesKeychain: cv.Auth.UseKeychain,
		AuthConfig:         authn.AuthConfig{Username: auth.Username, Password: auth.Password},
	}
	registryClientOpts := registryOpts.GetRegistryClientOpts(ctx)

	// set self-signed certificate
	if cv.Cert != nil {
		registryClientOpts = append(
			registryClientOpts,
			remote.WithTransport(
				&http.Transport{
					TLSClientConfig: &tls.Config{RootCAs: cv.Cert, MinVersion: tls.VersionTLS12},
				},
			),
		)
	}

	// apply registry client options
	opts.RegistryClientOpts = []ociremote.Option{
		ociremote.WithRemoteOptions(registryClientOpts...),
	}

	// set rekor options
	if verifyTlog {
		pubs, err := cv.getRekorPubKey(ctx)
		if err != nil {
			return nil, err
		}
		opts.RekorClient = cv.Rekor
		opts.RekorPubKeys = pubs
	}

	// set ct log options
	if verifySCT {
		ctPubs, err := cv.getCTLogPubKeys(ctx)
		if err != nil {
			return nil, fmt.Errorf("error getting ct log public keys: %s", err)
		}
		opts.CTLogPubKeys = ctPubs
	}

	return opts, nil
}

// gathers the requested trust roots and turns them into a
// verifier objects, which contains the public keys
// that are then used for the Cosign validation
func (cv *CosignValidator) verifiers(
	ctx context.Context,
	keyRefs []string,
) ([]Verifier, error) {
	trustRootsKeys, err := auth.GetTrustRoots(keyRefs, cv.TrustRoots, true)
	if err != nil {
		return nil, fmt.Errorf("error getting trust roots for validator %s: %s", cv.Name, err)
	}

	// Fall back to multiple verifiers
	verifiers := make([]Verifier, 0, len(keyRefs))
	for _, trustedKey := range trustRootsKeys {
		verifier, err := LoadVerifier(ctx, trustedKey)
		if err != nil {
			return nil, err
		}
		verifiers = append(verifiers, verifier)
	}
	return verifiers, nil
}

func (cv *CosignValidator) getRekorPubKey(ctx context.Context) (*cosign.TrustedTransparencyLogPubKeys, error) {
	if cv.rekorPubkey != nil {
		return cv.rekorPubkey, nil
	}
	pubs, err := cosign.GetRekorPubs(ctx)
	if err != nil {
		return nil, fmt.Errorf("error getting rekor public keys: %s", err)
	}

	return pubs, nil
}

func (cv *CosignValidator) getCTLogPubKeys(ctx context.Context) (*cosign.TrustedTransparencyLogPubKeys, error) {
	if cv.ctLogPubkey != nil {
		return cv.ctLogPubkey, nil
	}
	return cosign.GetCTLogPubs(ctx)
}

func (cv *CosignValidator) getFulcioCerts() (*x509.CertPool, *x509.CertPool, error) {
	if cv.fulcioCert != nil {
		return cv.fulcioCert, nil, nil
	}

	root, err := fulcio.GetRoots()
	if err != nil {
		return nil, nil, fmt.Errorf("error getting fulcio roots: %s", err)
	}
	intermediate, err := fulcio.GetIntermediates()
	if err != nil {
		return nil, nil, fmt.Errorf("error getting fulcio intermediates: %s", err)
	}

	return root, intermediate, nil
}
