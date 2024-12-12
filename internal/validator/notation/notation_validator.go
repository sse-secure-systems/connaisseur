package notation

import (
	"connaisseur/internal/image"
	"connaisseur/internal/policy"
	"connaisseur/internal/utils"
	"connaisseur/internal/validator/auth"
	"context"
	"crypto/tls"
	"crypto/x509"
	"fmt"
	"net/http"

	"github.com/notaryproject/notation-go"
	"github.com/notaryproject/notation-go/log"
	"github.com/notaryproject/notation-go/registry"
	"github.com/notaryproject/notation-go/verifier"
	"github.com/notaryproject/notation-go/verifier/trustpolicy"
	"github.com/notaryproject/notation-go/verifier/truststore"
	"github.com/sirupsen/logrus"
	"oras.land/oras-go/v2/registry/remote"
	orasAuth "oras.land/oras-go/v2/registry/remote/auth"
)

type NotationValidator struct {
	Name       string `validate:"required"`
	Type       string `validate:"eq=notation"`
	Auth       auth.Auth
	RootCA     *x509.CertPool
	TrustStore truststore.X509TrustStore
}

type NotationValidatorYaml struct {
	Name       string           `yaml:"name"`
	Type       string           `yaml:"type"`
	Auth       auth.Auth        `yaml:"auth"`
	Cert       string           `yaml:"cert"`
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

	imts, err := NewInMemoryTrustStore(valData.TrustRoots)
	if err != nil {
		return fmt.Errorf("failed to create trust store: %s", err)
	}

	if valData.Cert != "" {
		rootCA := x509.NewCertPool()
		if !rootCA.AppendCertsFromPEM([]byte(valData.Cert)) {
			return fmt.Errorf("failed to parse certificate")
		}
		nv.RootCA = rootCA
	}

	nv.Name = valData.Name
	nv.Type = valData.Type
	nv.Auth = valData.Auth
	nv.TrustStore = imts

	return nil
}

func (nv *NotationValidator) ValidateImage(
	ctx context.Context,
	image *image.Image,
	args policy.RuleOptions,
) (string, error) {
	trustPolicy, err := nv.setUpTrustPolicy(image, args)
	if err != nil {
		return "", fmt.Errorf("failed to set up trust policy: %s", err)
	}

	verifier, err := verifier.New(trustPolicy, nv.TrustStore, nil)
	if err != nil {
		return "", fmt.Errorf("failed to create verifier: %s", err)
	}

	remoteRepo, err := remote.NewRepository(image.Context().String())
	if err != nil {
		return "", fmt.Errorf("failed to create remote repository: %s", err)
	}

	client := orasAuth.DefaultClient
	if nv.RootCA != nil {
		client.Client = &http.Client{
			Transport: &http.Transport{
				TLSClientConfig: &tls.Config{
					RootCAs:    nv.RootCA,
					MinVersion: tls.VersionTLS12,
				},
			},
		}
	}

	if authn := nv.Auth.LookUp(image.Context().Name()); authn.Username != "" &&
		authn.Password != "" {
		client.Credential = func(notation_ctx context.Context, registry string) (orasAuth.Credential, error) {
			logrus.Debugf("requesting credentials for %s", registry)
			if registry == image.Context().RegistryStr() {
				return orasAuth.Credential{
					Username: authn.Username,
					Password: authn.Password,
				}, nil
			}
			return orasAuth.EmptyCredential, nil
		}
	}

	remoteRepo.Client = client
	remoteRegisty := registry.NewRepository(remoteRepo)

	// notation needs digests for signature verification
	// thus we resolve the digest if it is not set
	if image.Digest() == "" {
		desc, err := remoteRegisty.Resolve(ctx, image.Name())
		if err != nil {
			return "", fmt.Errorf("failed to resolve image tag: %s", err)
		}
		logrus.Debugf("resolved digest: %s", desc.Digest.String())
		image.SetDigest(desc.Digest.String())
	}

	verifyOptions := notation.VerifyOptions{
		ArtifactReference:    fmt.Sprintf("%s@%s", image.Context().String(), image.Digest()),
		MaxSignatureAttempts: 10,
	}

	notation_ctx := log.WithLogger(ctx, logrus.StandardLogger())
	digest, _, err := notation.Verify(notation_ctx, verifier, remoteRegisty, verifyOptions)
	if err != nil {
		return "", fmt.Errorf("failed to verify image: %s", err)
	}

	return string(digest.Digest), nil
}

func (nv *NotationValidator) setUpTrustPolicy(
	image *image.Image,
	args policy.RuleOptions,
) (*trustpolicy.Document, error) {
	imts := nv.TrustStore.(*InMemoryTrustStore)
	trs, err := auth.GetTrustRoots([]string{args.TrustRoot}, imts.trustRoots, true)
	if err != nil {
		return nil, fmt.Errorf("failed to get trust roots: %s", err)
	}

	vl := utils.StringDefault(args.VerificationLevel, trustpolicy.LevelStrict.Name)
	vt := trustpolicy.TimestampOption(
		utils.StringDefault(args.VerifyTimestamp, string(trustpolicy.OptionAlways)),
	)

	// construct trust store strings
	tss := []string{}
	for _, tr := range trs {
		tss = append(tss, fmt.Sprintf("%s:%s", truststore.TypeCA, tr.Name))

		if tr.TSCert != "" {
			tss = append(tss, fmt.Sprintf("%s:%s", truststore.TypeTSA, tr.Name))
		}
	}

	return &trustpolicy.Document{
		Version: "1.0",
		TrustPolicies: []trustpolicy.TrustPolicy{
			{
				Name:           "default",
				RegistryScopes: []string{image.Context().String()},
				SignatureVerification: trustpolicy.SignatureVerification{
					VerificationLevel: vl,
					VerifyTimestamp:   vt,
				},
				TrustStores:       tss,
				TrustedIdentities: []string{"*"},
			},
		},
	}, nil
}
