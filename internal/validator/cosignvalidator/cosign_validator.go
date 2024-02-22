package cosignvalidator

import (
	"connaisseur/internal/constants"
	"connaisseur/internal/image"
	"connaisseur/internal/policy"
	"connaisseur/internal/utils"
	"connaisseur/internal/validator/auth"
	"context"
	"crypto"
	"crypto/tls"
	"crypto/x509"
	"encoding/json"
	"fmt"
	"net/http"
	"net/url"
	"os"
	"strings"

	"github.com/google/go-containerregistry/pkg/authn"
	"github.com/google/go-containerregistry/pkg/v1/remote"
	"github.com/sigstore/cosign/v2/cmd/cosign/cli/options"
	"github.com/sigstore/cosign/v2/cmd/cosign/cli/rekor"
	"github.com/sigstore/cosign/v2/cmd/cosign/cli/sign"
	"github.com/sigstore/cosign/v2/pkg/cosign"
	"github.com/sigstore/cosign/v2/pkg/oci"
	ociremote "github.com/sigstore/cosign/v2/pkg/oci/remote"
	sigs "github.com/sigstore/cosign/v2/pkg/signature"
	sig "github.com/sigstore/sigstore/pkg/signature"
	"github.com/sirupsen/logrus"
)

type CosignValidator struct {
	// Name of the validator
	Name string `validate:"required"`
	// type of the validator (will always be "cosign")
	Type string `validate:"eq=cosign"`
	// url of the Rekor instance
	Rekor string `validate:"url"`
	// self signed certificate of the registry
	Cert string
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
		Rekor string `yaml:"rekor"`
	}
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

// Unmarshals the yaml into a CosignValidator object, validating
// some attributes in the process
func (cv *CosignValidator) UnmarshalYAML(unmarshal func(interface{}) error) error {
	var valData CosignValidatorYaml
	if err := unmarshal(&valData); err != nil {
		return err
	}

	// validate rekor url
	if valData.Host.Rekor != "" {
		if !utils.HasPrefixes(strings.ToLower(valData.Host.Rekor), "http://", "https://") {
			valData.Host.Rekor = fmt.Sprintf("https://%s", valData.Host.Rekor)
		}

		_, err := url.ParseRequestURI(valData.Host.Rekor)

		if err != nil {
			return fmt.Errorf("invalid url for rekor: %s", err)
		}
	} else {
		valData.Host.Rekor = constants.DefaultRekorHost
	}

	// validate trust roots
	if len(valData.TrustRoots) < 1 {
		return fmt.Errorf("no trust roots provided for validator %s", valData.Name)
	}

	if valData.Cert != "" {
		certPool := x509.NewCertPool()
		if !certPool.AppendCertsFromPEM([]byte(valData.Cert)) {
			return fmt.Errorf("invalid certificate for validator %s", valData.Name)
		}
	}

	cv.Name = valData.Name
	cv.Type = valData.Type
	cv.Rekor = valData.Host.Rekor
	cv.Cert = valData.Cert
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

	// get verifiers for public keys
	verifiers, err := cv.verifiers(
		ctx,
		trustRootReferences,
	)
	if err != nil {
		return "", fmt.Errorf("error getting verifiers: %s", err)
	}
	type verifierOutput struct {
		checkedSignatures   []oci.Signature
		err                 error
		validatingTrustRoot string
	}
	numberOfTrustRoots := len(verifiers)
	verifierOutputChannel := make(chan verifierOutput, numberOfTrustRoots)
	for _, verifier := range verifiers {
		go func(verifier KeyVerifierTuple, verifierOutputChannel chan<- verifierOutput) {
			// configure validation options
			opts, err := cv.setupOptions(ctx, args, img, verifier.Verifier)
			if err != nil {
				verifierOutputChannel <- verifierOutput{nil, fmt.Errorf("error setting up cosign options: %s", err), ""}
				return
			}
			logrus.Debugf("validating image %s with trust root %s", imageRef, verifier.Name)
			// do cosign validation on image
			validSignatures, _, err := cosign.VerifyImageSignatures(
				ctx,
				imageRef,
				opts,
			)
			if err != nil {
				// short-circuit if the image doesn't exist
				if strings.HasPrefix(err.Error(), "image tag not found:") {
					msg := fmt.Sprintf("image %s does not exist: %s", imageRef, err)
					logrus.Info(msg)
					verifierOutputChannel <- verifierOutput{nil, fmt.Errorf(msg), ""}
					return
				}
				logrus.Debugf("error verifying signatures with verifier for trust root %s: %s", verifier.Name, err)
				// propagating an error is explicitly not done since at this point it is not entirely clear if an actual error should be thrown. This can only be determined after all other verifier instances have been checked for as well; therefore, error nil is sent to the channel
				verifierOutputChannel <- verifierOutput{nil, nil, ""}
				return
			}
			verifierOutputChannel <- verifierOutput{validSignatures, nil, verifier.Name}
		}(verifier, verifierOutputChannel)
	}
	validatingTrustRoots := []string{}
	checkedSignatures := []oci.Signature{}
	for i := 0; i < numberOfTrustRoots; i++ {
		output := <-verifierOutputChannel
		if output.err != nil {
			return "", output.err
		}
		checkedSignatures = append(checkedSignatures, output.checkedSignatures...)
		validatingTrustRoots = append(validatingTrustRoots, output.validatingTrustRoot)
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
	if args.Required != nil && len(args.Required) > 0 {
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

	// no signed digests
	return "", fmt.Errorf("no signed digests")
}

// sets up the options for the Cosign validation, which includes
// turning the trust roots into verifiers, adding authentication
// and setting self-signed certificates
func (cv *CosignValidator) setupOptions(
	ctx context.Context,
	args policy.RuleOptions,
	img *image.Image,
	verifier sig.Verifier,
) (*cosign.CheckOpts, error) {
	var ignoreTlog bool
	if args.VerifyTLog == nil {
		ignoreTlog = false
	} else {
		ignoreTlog = !*args.VerifyTLog
	}
	opts := &cosign.CheckOpts{SigVerifier: verifier, IgnoreTlog: ignoreTlog}

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
	if cv.Cert != "" {
		certPool := x509.NewCertPool()
		// certificate was already validated during unmarshalling
		_ = certPool.AppendCertsFromPEM([]byte(cv.Cert))
		registryClientOpts = append(
			registryClientOpts,
			remote.WithTransport(
				&http.Transport{
					TLSClientConfig: &tls.Config{RootCAs: certPool, MinVersion: tls.VersionTLS12},
				},
			),
		)
	}

	// apply registry client options
	opts.RegistryClientOpts = []ociremote.Option{
		ociremote.WithRemoteOptions(registryClientOpts...),
	}

	if cv.Rekor != "" && !ignoreTlog {
		rekorClient, err := rekor.NewClient(cv.Rekor)
		if err != nil { // Currently cannot happen as it only fails for invalid URLs, which are already caught during unmarshalling
			return nil, fmt.Errorf("unable to create Rekor client for %s: %s", cv.Rekor, err)
		}
		opts.RekorClient = rekorClient

		// env var is needed, otherwise cosign tries to create files in readonly FS, which will fail
		_ = os.Setenv("SIGSTORE_NO_CACHE", "1")
		pubs, err := cosign.GetRekorPubs(ctx)
		if err != nil {
			return nil, fmt.Errorf("error getting rekor public keys: %s", err)
		}
		opts.RekorPubKeys = pubs
	}

	return opts, nil
}

type KeyVerifierTuple struct {
	// name of the trust root
	Name string
	// verifier for the public keys
	Verifier sig.Verifier
}

// Loads a public key from a key inline key or a key reference.
func LoadKeyVerifierTuple(
	ctx context.Context,
	trustRoot auth.TrustRoot,
) (KeyVerifierTuple, error) {
	var (
		verifier sig.Verifier
		err      error
	)
	hashAlgorithm := crypto.SHA256

	if strings.HasPrefix(trustRoot.Key, "-----BEGIN PUBLIC KEY-----") {
		verifier, err = sigs.LoadPublicKeyRaw([]byte(trustRoot.Key), hashAlgorithm)
	} else {
		verifier, err = sigs.PublicKeyFromKeyRefWithHashAlgo(ctx, trustRoot.Key, hashAlgorithm)
	}

	return KeyVerifierTuple{
		Name:     trustRoot.Name,
		Verifier: verifier,
	}, err
}

// gathers the requested trust roots and turns them into a
// verifier objects, which contains the public keys
// that are then used for the Cosign validation
func (cv *CosignValidator) verifiers(
	ctx context.Context,
	keyRefs []string,
) ([]KeyVerifierTuple, error) {
	trustRootsKeys, err := auth.GetTrustRoots(keyRefs, cv.TrustRoots, true)
	if err != nil {
		return nil, fmt.Errorf("error getting trust roots for validator %s: %s", cv.Name, err)
	}

	// Fall back to multiple verifiers
	verifiers := make([]KeyVerifierTuple, 0, len(keyRefs))
	for _, trustedKey := range trustRootsKeys {
		tuple, err := LoadKeyVerifierTuple(ctx, trustedKey)
		if err != nil {
			return nil, err
		}
		verifiers = append(verifiers, tuple)
	}
	return verifiers, nil
}
