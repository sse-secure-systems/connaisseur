package notaryv1

import (
	"connaisseur/internal/constants"
	"connaisseur/internal/image"
	"connaisseur/internal/policy"
	"connaisseur/internal/utils"
	"connaisseur/internal/validator/auth"
	"connaisseur/internal/validator/notaryv1/notaryserver"
	"context"
	"crypto/x509"
	"encoding/hex"
	"encoding/pem"
	"fmt"
	"net/url"
	"reflect"
	"strings"

	dgst "github.com/opencontainers/go-digest"
	"github.com/sirupsen/logrus"
	"github.com/theupdateframework/notary"
	"github.com/theupdateframework/notary/tuf/data"
)

type NotaryV1Validator struct {
	Name       string `validate:"required"`
	Type       string `validate:"eq=notaryv1"`
	Host       string `validate:"url"`
	Cert       string
	Auth       auth.Auth
	TrustRoots []auth.TrustRoot `validate:"min=1,dive"`
}

type NotaryV1ValidatorYaml struct {
	Name       string           `yaml:"name"`
	Type       string           `yaml:"type"`
	Host       string           `yaml:"host"`
	Cert       string           `yaml:"cert"`
	Auth       auth.Auth        `yaml:"auth"`
	TrustRoots []auth.TrustRoot `yaml:"trustRoots"`
}

func (nv1v *NotaryV1Validator) UnmarshalYAML(unmarshal func(interface{}) error) error {
	var valData NotaryV1ValidatorYaml
	if err := unmarshal(&valData); err != nil {
		return err
	}

	if len(valData.TrustRoots) < 1 {
		return fmt.Errorf("no trust roots provided for validator %s", valData.Name)
	}

	if valData.Host != "" {
		if !utils.HasPrefixes(strings.ToLower(valData.Host), "http://", "https://") {
			// we default to use https for notary servers, if no protocol given
			valData.Host = fmt.Sprintf("https://%s", valData.Host)
		}

		_, err := url.ParseRequestURI(valData.Host)

		if err != nil {
			return fmt.Errorf("invalid url for notary host: %s", err)
		}
	} else {
		valData.Host = "https://" + constants.DefaultNotaryHost
	}

	// if the secret does not contain a 'registry' key, we want to set the URL to the validator's host URL
	if len(valData.Auth.AuthConfigs) == 1 {
		if v, ok := valData.Auth.AuthConfigs[constants.EmptyAuthRegistry]; ok {
			rr, err := image.NewRegistryRepo(valData.Host)
			if err != nil {
				return fmt.Errorf("unable to parse registry %s: %v", valData.Host, err)
			}
			delete(valData.Auth.AuthConfigs, constants.EmptyAuthRegistry)
			valData.Auth.AuthConfigs[rr.String()] = v
		}
	}

	if valData.Cert != "" {
		certPool := x509.NewCertPool()
		if !certPool.AppendCertsFromPEM([]byte(valData.Cert)) {
			return fmt.Errorf("invalid certificate for validator %s", valData.Name)
		}
	}

	nv1v.Name = valData.Name
	nv1v.Type = valData.Type
	nv1v.Host = valData.Host
	nv1v.Cert = valData.Cert
	nv1v.Auth = valData.Auth
	nv1v.TrustRoots = valData.TrustRoots
	return nil
}

func (nv1v *NotaryV1Validator) ValidateImage(
	ctx context.Context,
	image *image.Image,
	args policy.RuleOptions,
) (string, error) {
	nc, err := notaryserver.NewNotaryClient(nv1v.Host, nv1v.Cert, nv1v.Auth, image)
	if err != nil {
		return "", fmt.Errorf("error creating notary client: %s", err)
	}

	// create empty repo, then download all trust data
	repo := &notaryserver.Repo{}
	err = repo.DownloadBaseTrustData(ctx, nc)
	if err != nil {
		return "", fmt.Errorf("error downloading trust data: %s", err)
	}
	logrus.Debug("Successfully downloaded trust data")

	// get root keys
	rootKeys, err := nv1v.trustRootKeys(args.TrustRoot)
	if err != nil {
		return "", fmt.Errorf("error getting trust root keys for validator %s: %s", nv1v.Name, err)
	}

	// validate all base trust data
	err = repo.ValidateBaseTrustData(rootKeys)
	if err != nil {
		return "", fmt.Errorf("error validating trust data: %s", err)
	}

	// gather targets to choose and potentially download them
	targets := []string{}
	// there are no delegations, so we can just use the canonical targets role
	if (args.Delegations == nil ||
		len(args.Delegations) < 1) && !repo.HasDelegations() {
		targets = append(targets, data.CanonicalTargetsRole.String())
	} else { // there are delegations, so we need to download+validate them
		if !repo.HasDelegations() {
			return "", fmt.Errorf("no delegations found for validator %s, but following were required: %+v", nv1v.Name, args.Required)
		}

		if len(args.Delegations) > 0 {
			reqDelegations := utils.Map[string, string](args.Delegations, func(s string) string { return toDelegationString(s) })
			targets = append(targets, reqDelegations...)
		} else {
			targets = append(targets, toDelegationString("releases"))
		}
		err := repo.DownloadAndValidateDelegations(ctx, nc, targets)
		if err != nil {
			// edge case: the targets role might already have delegations defined, but the actual files are missing.
			// this happens when the delegation are added as signers, but are not used to actually sign anything.
			// in this case, we need to take the targets role, as if no delegations were present
			if strings.Contains(err.Error(), "error acquiring trust data") && !repo.HasDelegationHashes(targets) {
				targets = []string{data.CanonicalTargetsRole.String()}
			} else {
				return "", fmt.Errorf("error during download and validation of delegations for targets: %+q", targets)
			}
		}
	}

	// look for digest in targets
	logrus.Debugf("Searching in %+v for digest for image %s", targets, image.OriginalString())
	digests := map[string]struct{}{}
	for _, target := range targets {
		var (
			digest    string
			digestErr error
		)
		signedTarget := repo.Targets[target].Signed

		// search trust data for either tag or digest
		if image.Tag() != "" {
			digest, digestErr = searchTargetsForTag(signedTarget, image.Tag())
			if digestErr != nil {
				return "", fmt.Errorf("validated targets don't contain reference: %s", digestErr)
			}

			// handle special case where the input image has tag and digest
			// there, make sure digest for tag matches given digest
			if image.Digest() != "" && image.Digest() != digest {
				return "", fmt.Errorf("digest %s resolved for tag %s doesn't match given digest %s", digest, image.Tag(), image.Digest())
			}
		} else {
			digest, digestErr = searchTargetsForDigest(signedTarget, image.Digest())
			if digestErr != nil {
				return "", fmt.Errorf("validated targets don't contain reference: %s", digestErr)
			}
		}

		logrus.Debugf("Found digest %s for image %s", digest, image.String())
		digests[digest] = struct{}{}
	}

	// make sure there is only one digest
	if len(digests) != 1 {
		return "", fmt.Errorf(
			"validator %s found %d digests for image %s, expected 1",
			nv1v.Name,
			len(digests),
			image.Identifier(),
		)
	}

	// return the digest
	keys := make([]string, 0, len(digests))
	for k := range digests {
		keys = append(keys, k)
	}
	return keys[0], nil
}

// trustRootKeys returns the keys of the auth.TrustRoots that match keyRef.
// If keyRef is the all quantifier '*', this is the list of all keys in the validator.
func (nv1v *NotaryV1Validator) trustRootKeys(keyRef string) ([]data.PublicKey, error) {
	trs, err := auth.GetTrustRoots([]string{keyRef}, nv1v.TrustRoots, true)
	if err != nil {
		return nil, fmt.Errorf("error getting keys for validator %s: %s", nv1v.Name, err)
	}
	keys := []data.PublicKey{}

	for _, tr := range trs {
		pubDecode, rest := pem.Decode([]byte(tr.Key))
		pub, err := x509.ParsePKIXPublicKey(pubDecode.Bytes)
		if err != nil {
			return nil, fmt.Errorf("error parsing public key %s: %s", tr.Name, err)
		}
		if len(rest) != 0 {
			msg := fmt.Sprintf("key material for key %s of validator %s contains extraneous characters", tr.Name, nv1v.Name)
			logrus.Error(msg)
			return nil, fmt.Errorf(msg)
		}

		var alg string
		switch keyType := reflect.TypeOf(pub).String(); keyType {
		case "*rsa.PublicKey":
			alg = "rsa"
		case "*ecdsa.PublicKey":
			alg = "ecdsa"
		default:
			alg = "unknown"
		}

		keys = append(keys, data.NewPublicKey(alg, pubDecode.Bytes))
	}

	return keys, nil
}

func toDelegationString(delegation string) string {
	if strings.HasPrefix(delegation, "targets/") {
		return delegation
	}
	return fmt.Sprintf("targets/%s", delegation)
}

func searchTargetsForTag(targetFile data.Targets, tag string) (string, error) {
	logrus.Debugf("searching targets for tag %s", tag)

	for key, target := range targetFile.Targets {
		if key != tag {
			continue
		}

		return dgst.NewDigestFromEncoded(
			notary.SHA256,
			hex.EncodeToString(target.Hashes[notary.SHA256]),
		).String(), nil
	}

	return "", fmt.Errorf("no tag '%s' found in targets", tag)
}

func searchTargetsForDigest(targetFile data.Targets, digest string) (string, error) {
	logrus.Debugf("searching targets for digest %s", digest)

	for _, target := range targetFile.Targets {
		targetDigest := dgst.NewDigestFromEncoded(
			notary.SHA256,
			hex.EncodeToString(target.Hashes[notary.SHA256]),
		)
		if targetDigest.String() == digest {
			return targetDigest.String(), nil
		}
	}

	return "", fmt.Errorf("no digest '%s' found in targets", digest)
}
