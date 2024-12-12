package notation

import (
	"connaisseur/internal/image"
	"connaisseur/internal/policy"
	"connaisseur/internal/utils"
	"connaisseur/internal/validator/auth"
	"context"
	"fmt"

	"github.com/notaryproject/notation-go"
	"github.com/notaryproject/notation-go/registry"
	"github.com/notaryproject/notation-go/verifier"
	"github.com/notaryproject/notation-go/verifier/trustpolicy"
	"github.com/notaryproject/notation-go/verifier/truststore"
	"oras.land/oras-go/v2/registry/remote"
	orasAuth "oras.land/oras-go/v2/registry/remote/auth"
)

type NotationValidator struct {
	Name       string `validate:"required"`
	Type       string `validate:"eq=notation"`
	Auth       auth.Auth
	TrustStore truststore.X509TrustStore
}

type NotationValidatorYaml struct {
	Name       string           `yaml:"name"`
	Type       string           `yaml:"type"`
	Auth       auth.Auth        `yaml:"auth"`
	TrustRoots []auth.TrustRoot `yaml:"trustRoots"`
}

func (nv *NotationValidator) UnmarshalYAML(unmarshal func(interface{}) error) error {
	var valData NotationValidatorYaml
	if err := unmarshal(&valData); err != nil {
		return err
	}

	if len(valData.TrustRoots) < 1 {
		return fmt.Errorf("no trust roots provided for validator %s", valData.Name)
	}

	nv.Name = valData.Name
	nv.Type = valData.Type
	nv.Auth = valData.Auth
	nv.TrustStore = &InMemoryTrustStore{
		trustRoots: valData.TrustRoots,
	}
	return nil
}

func (nv *NotationValidator) ValidateImage(
	ctx context.Context,
	image *image.Image,
	args policy.RuleOptions,
) (string, error) {

	trustPolicy, err := nv.setUpTrustPolicy(image.Name(), args)
	if err != nil {
		return "", fmt.Errorf("failed to set up trust policy: %s", err)
	}

	verifier, err := verifier.New(trustPolicy, nv.TrustStore, nil)
	if err != nil {
		return "", fmt.Errorf("failed to create verifier: %s", err)
	}

	remoteRepo, err := remote.NewRepository(image.Name())
	if err != nil {
		return "", fmt.Errorf("failed to create remote repository: %s", err)
	}

	if authn := nv.Auth.LookUp(image.Context().Name()); authn.Username != "" &&
		authn.Password != "" {
		client := orasAuth.DefaultClient
		client.Credential = func(nv2_ctx context.Context, s string) (orasAuth.Credential, error) {
			return orasAuth.Credential{
				Username: authn.Username,
				Password: authn.Password,
			}, nil
		}
		remoteRepo.Client = client
	}
	remoteRegisty := registry.NewRepository(remoteRepo)

	if image.Digest() == "" {
		desc, err := remoteRegisty.Resolve(ctx, image.Name())
		if err != nil {
			return "", fmt.Errorf("failed to resolve image tag: %s", err)
		}
		image.SetDigest(desc.Digest.String())
	}

	verifyOptions := notation.VerifyOptions{
		ArtifactReference:    image.Name(),
		MaxSignatureAttempts: 10,
	}

	digest, _, err := notation.Verify(ctx, verifier, remoteRegisty, verifyOptions)
	if err != nil {
		return "", fmt.Errorf("failed to verify image: %s", err)
	}

	return string(digest.Digest), nil
}

func (nv2v *NotationValidator) setUpTrustPolicy(
	image string,
	args policy.RuleOptions,
) (*trustpolicy.Document, error) {
	imtr := nv2v.TrustStore.(*InMemoryTrustStore)
	trs, err := auth.GetTrustRoots([]string{args.TrustRoot}, imtr.trustRoots, true)
	if err != nil {
		return nil, fmt.Errorf("failed to get trust roots: %s", err)
	}

	return &trustpolicy.Document{
		Version: "1.0",
		TrustPolicies: []trustpolicy.TrustPolicy{
			{
				Name:           "default",
				RegistryScopes: []string{image},
				SignatureVerification: trustpolicy.SignatureVerification{
					VerificationLevel: trustpolicy.LevelStrict.Name,
				},
				TrustStores: utils.Map(
					trs,
					func(tr auth.TrustRoot) string {
						return fmt.Sprintf("ca:%s", tr.Name)
					},
				),
				TrustedIdentities: []string{"*"},
			},
		},
	}, nil
}
