package notation

import (
	"connaisseur/internal/image"
	"connaisseur/internal/policy"
	"connaisseur/test/testhelper"
	"context"
	"io"
	"os"
	"strings"
	"testing"

	"github.com/notaryproject/notation-go/verifier/trustpolicy"
	"github.com/sirupsen/logrus"
	"github.com/stretchr/testify/assert"
	"gopkg.in/yaml.v3"
)

const PRE = "../../../test/testdata/notation/"

func TestMain(m *testing.M) {
	logrus.SetOutput(io.Discard)
	os.Exit(m.Run())
}

func TestUnmarshal(t *testing.T) {
	var testCases = []struct {
		file       string
		name       string
		trustRoots []string
		err        string
	}{
		{ // 1: simple working case
			"01_notation",
			"ghcr-notation",
			[]string{"default", "different-cert"},
			"",
		},
		{ // 2: missing trust roots
			"02_no_trust_root",
			"",
			[]string{},
			"no trust roots provided for validator",
		},
		{ // 3: unmarshal error
			"03_unmarshal_err",
			"",
			[]string{},
			"yaml: unmarshal errors",
		},
		{ // 4: invalid certificate
			"04_invalid_cert",
			"",
			[]string{},
			"failed to parse certificate",
		},
		{ // 5: missing certificate
			"05_missing_cert",
			"",
			[]string{},
			"no certificate provided",
		},
		{ // 6: decode error on certificate
			"06_decode_cert_err",
			"",
			[]string{},
			"failed to decode certificate",
		},
		{ // 7: decode error on tsa certificate
			"09_decode_tsa_cert_err",
			"",
			[]string{},
			"failed to decode certificate",
		},
	}

	for idx, tc := range testCases {
		var nv NotationValidator

		nvBytes, _ := os.ReadFile(PRE + tc.file + ".yaml")
		err := yaml.Unmarshal(nvBytes, &nv)

		if tc.err != "" {
			assert.NotNil(t, err, idx+1)
			assert.ErrorContains(t, err, tc.err, idx+1)
		} else {
			assert.Nil(t, err, idx+1)
			assert.Equal(t, tc.name, nv.Name, idx+1)
			assert.Equal(t, "notation", nv.Type, idx+1)
			assert.Len(t, nv.TrustStore.(*InMemoryTrustStore).trustRoots, len(tc.trustRoots), idx+1)
			assert.Len(t, nv.TrustStore.(*InMemoryTrustStore).certs, len(tc.trustRoots), idx+1)

			for i, tr := range tc.trustRoots {
				assert.Equal(t, tr, nv.TrustStore.(*InMemoryTrustStore).trustRoots[i].Name, idx+1)
			}
		}
	}
}

func TestValidateImage(t *testing.T) {
	var testCases = []struct {
		file   string
		image  string
		args   policy.RuleOptions
		digest string
		err    string
	}{
		{ // 1: simple working case
			"07_selfsigned_cert",
			"sse-secure-systems/testimage:notation-sign",
			policy.RuleOptions{},
			"sha256:a136cc4e785798e5e8483047cf621cf0a0300a93d47703a3f066c340c070f5cf",
			"",
		},
		{ // 2: no signature
			"07_selfsigned_cert",
			"sse-secure-systems/testimage:notation-unsign",
			policy.RuleOptions{},
			"",
			"no signature is associated",
		},
		{ // 3: simple working case
			"07_selfsigned_cert",
			"sse-secure-systems/testimage:notation-sign",
			policy.RuleOptions{VerificationLevel: "audit"},
			"sha256:a136cc4e785798e5e8483047cf621cf0a0300a93d47703a3f066c340c070f5cf",
			"",
		},
		{ // 4: wrong key
			"07_selfsigned_cert",
			"sse-secure-systems/testimage:notation-sign",
			policy.RuleOptions{TrustRoot: "different-cert"},
			"",
			"failed to verify signature",
		},
	}

	reg := testhelper.NotationMockRegistry(PRE)
	defer reg.Close()

	for idx, tc := range testCases {
		var nv NotationValidator

		nvBytes, _ := os.ReadFile(PRE + tc.file + ".yaml")
		yaml.Unmarshal(nvBytes, &nv)

		img, err := image.New(strings.TrimPrefix(reg.URL, "https://") + "/" + tc.image)
		assert.NoError(t, err, idx+1)
		digest, err := nv.ValidateImage(context.Background(), img, tc.args)

		if tc.err != "" {
			assert.NotNil(t, err, idx+1)
			assert.ErrorContains(t, err, tc.err, idx+1)
		} else {
			assert.Nil(t, err, idx+1)
			assert.Equal(t, tc.digest, digest, idx+1)
		}
	}
}

func TestSetUpTrustPolicy(t *testing.T) {
	var testCases = []struct {
		file              string
		image             string
		args              policy.RuleOptions
		registryScope     string
		trustStores       []string
		verificationLevel string
		VerifyTimestamp   trustpolicy.TimestampOption
		err               string
	}{
		{ // 1: simple working case
			"01_notation",
			"ghcr.io/test/test:latest",
			policy.RuleOptions{},
			"ghcr.io/test/test",
			[]string{"ca:default"},
			trustpolicy.LevelStrict.Name,
			trustpolicy.OptionAlways,
			"",
		},
		{ // 2: named trust root
			"01_notation",
			"ghcr.io/test/test:latest",
			policy.RuleOptions{TrustRoot: "different-cert"},
			"ghcr.io/test/test",
			[]string{"ca:different-cert"},
			trustpolicy.LevelStrict.Name,
			trustpolicy.OptionAlways,
			"",
		},
		{ // 3: missing trust root
			"01_notation",
			"ghcr.io/test/test:latest",
			policy.RuleOptions{TrustRoot: "missing"},
			"",
			[]string{},
			"",
			trustpolicy.OptionAlways,
			"failed to get trust roots",
		},
		{ // 4: testing verification level
			"01_notation",
			"ghcr.io/test/test:latest",
			policy.RuleOptions{VerificationLevel: "audit"},
			"ghcr.io/test/test",
			[]string{"ca:default"},
			trustpolicy.LevelAudit.Name,
			trustpolicy.OptionAlways,
			"",
		},
		{ // 5: testing timestamp verification
			"01_notation",
			"ghcr.io/test/test:latest",
			policy.RuleOptions{VerifyTimestamp: "afterCertExpiry"},
			"ghcr.io/test/test",
			[]string{"ca:default"},
			trustpolicy.LevelStrict.Name,
			trustpolicy.OptionAfterCertExpiry,
			"",
		},
		{ // 6: tesing tsa
			"08_tsa_cert",
			"ghcr.io/test/test:latest",
			policy.RuleOptions{},
			"ghcr.io/test/test",
			[]string{"ca:default", "tsa:default"},
			trustpolicy.LevelStrict.Name,
			trustpolicy.OptionAlways,
			"",
		},
	}

	for idx, tc := range testCases {
		var nv NotationValidator

		nvBytes, _ := os.ReadFile(PRE + tc.file + ".yaml")
		yaml.Unmarshal(nvBytes, &nv)

		img, _ := image.New(tc.image)
		tpd, err := nv.setUpTrustPolicy(img, tc.args)

		if tc.err != "" {
			assert.NotNil(t, err, idx+1)
			assert.ErrorContains(t, err, tc.err, idx+1)
		} else {
			assert.Nil(t, err, idx+1)

			tp := tpd.TrustPolicies[0]
			assert.Equal(t, tc.registryScope, tp.RegistryScopes[0], idx+1)
			assert.Len(t, tp.TrustStores, len(tc.trustStores), idx+1)
			for i, tr := range tc.trustStores {
				assert.Equal(t, tr, tp.TrustStores[i], idx+1)
			}
			assert.Equal(t, tc.verificationLevel, tp.SignatureVerification.VerificationLevel, idx+1)
			assert.Equal(t, tc.VerifyTimestamp, tp.SignatureVerification.VerifyTimestamp, idx+1)
		}
	}
}
