package cosignvalidator

import (
	"connaisseur/internal/constants"
	"connaisseur/internal/image"
	"connaisseur/internal/policy"
	"connaisseur/test/testhelper"
	"context"
	"crypto/ecdsa"
	"fmt"
	"io"
	"os"
	"strings"
	"testing"

	"github.com/sigstore/cosign/v2/pkg/oci/remote"
	"github.com/sirupsen/logrus"
	"github.com/stretchr/testify/assert"
	"gopkg.in/yaml.v3"
)

const PRE = "../../../test/testdata/cosign/"

func TestMain(m *testing.M) {
	constants.SecretsDir = "../../../test/testdata/auth/"
	logrus.SetOutput(io.Discard)
	os.Exit(m.Run())
}

func TestValidator(t *testing.T) {
	var testCases = []struct {
		file       string
		name       string
		trustRoots []string
		err        string
	}{
		{ // 1: working case
			"01_cosign",
			"default",
			[]string{"alice", "bob"},
			"",
		},
		{ // 2: working case with rekor
			"02_rekor",
			"rekor",
			[]string{"default"},
			"",
		},
		{ // 3: unmarshal error
			"03_unmarshal_err",
			"",
			[]string{},
			"yaml: unmarshal errors",
		},
		{ // 4: invalid rekor url error
			"04_rekor_err",
			"",
			[]string{},
			"unable to create Rekor client",
		},
		{ // 5: no trust roots error
			"05_no_trust_roots",
			"",
			[]string{},
			"no trust roots provided for validator",
		},
		{ // 6: invalid certificate error
			"10_invalid_cert",
			"",
			[]string{},
			"invalid certificate",
		},
		{ // 7: working case with keyless
			"11_keyless",
			"default",
			[]string{"philipp-keyless", "bob-keyless"},
			"",
		},
		{ // 8: invalid rekor public key error
			"12_invalid_rekor_pub_key",
			"",
			[]string{},
			"error adding rekor public key",
		},
		{ // 9: invalid fulcio certificate error
			"13_invalid_fulcio_cert",
			"",
			[]string{},
			"invalid fulcio certificate",
		},
		{ // 10: invalid ct log pub key error
			"14_invalid_ct_log_pub_key",
			"",
			[]string{},
			"error adding ct log public key",
		},
	}

	for idx, tc := range testCases {
		var cv CosignValidator

		cvBytes, _ := os.ReadFile(PRE + tc.file + ".yaml")
		err := yaml.Unmarshal(cvBytes, &cv)

		if tc.err != "" {
			assert.NotNil(t, err, idx+1)
			assert.ErrorContains(t, err, tc.err, idx+1)
		} else {
			assert.Nil(t, err, idx+1)
			assert.Equal(t, tc.name, cv.Name, idx+1)
			for i, tr := range tc.trustRoots {
				assert.Contains(t, tr, cv.TrustRoots[i].Name, idx+1)
			}
		}
	}
}

func TestVerifiers(t *testing.T) {
	var testCases = []struct {
		file       string
		keyRefs    []string
		expPubKeys []int64
		expErr     string
	}{
		{
			"01_cosign",
			[]string{"alice"},
			[]int64{-3916471775317094451},
			"",
		},
		{
			"01_cosign",
			[]string{"bob"},
			[]int64{-7384356341354458600},
			"",
		},
		{
			"01_cosign",
			[]string{"alice", "bob"},
			[]int64{-3916471775317094451, -7384356341354458600},
			"",
		},
		{
			"01_cosign",
			[]string{"*"},
			[]int64{-3916471775317094451, -7384356341354458600},
			"",
		},
		{
			"09_full_config",
			nil,
			[]int64{-7401950337678553810},
			"",
		},
		{
			"09_full_config",
			[]string{},
			[]int64{-7401950337678553810},
			"",
		},
		{ // Missing specific trust root
			"09_full_config",
			[]string{"charlie"},
			[]int64{},
			"error getting trust roots for validator",
		},
		{ // Missing default trust root
			"01_cosign",
			[]string{},
			[]int64{},
			"error getting trust roots for validator",
		},
	}

	ctx := context.Background()

	for _, tc := range testCases {
		var cv CosignValidator
		cvBytes, _ := os.ReadFile(PRE + tc.file + ".yaml")
		err := yaml.Unmarshal(cvBytes, &cv)
		assert.Nil(t, err)

		verifiers, err := cv.verifiers(ctx, tc.keyRefs)

		if tc.expErr != "" {
			assert.NotNil(t, err)
			assert.ErrorContains(t, err, tc.expErr)
		} else {
			assert.Nil(t, err)
			assert.Equal(t, len(tc.expPubKeys), len(verifiers))

			for i, verifier := range verifiers {
				pubKey, _ := verifier.KeyVerifier.PublicKey()
				assert.Equal(t, tc.expPubKeys[i], pubKey.(*ecdsa.PublicKey).X.Int64())
			}
		}
	}
}

func TestSetupOptions(t *testing.T) {
	falseVar, trueVar := false, true
	// Testing which options are present is hard as they're wrapped in a private options object
	// but we can at least see that nothing obvious breaks
	var testCases = []struct {
		file          string
		opts          policy.RuleOptions
		expIgnoreTlog bool
		expIgnoreSCT  bool
		expUser       string
		expPass       string
		expRekorKeys  map[string]int64
		expCTLogKeys  map[string]int64
	}{
		{ // 1: no options
			"01_cosign",
			policy.RuleOptions{},
			false,
			false,
			"",
			"",
			nil,
			nil,
		},
		{ // 2: ignore tlog false
			"01_cosign",
			policy.RuleOptions{VerifyTLog: &trueVar},
			false,
			false,
			"",
			"",
			nil,
			nil,
		},
		{ // 3: ignore tlog true
			"01_cosign",
			policy.RuleOptions{VerifyTLog: &falseVar},
			true,
			false,
			"",
			"",
			nil,
			nil,
		},
		{ // 4: authentication
			"06_auth",
			policy.RuleOptions{},
			false,
			false,
			"user",
			"pass",
			nil,
			nil,
		},
		{ // 5: ignore sct true
			"01_cosign",
			policy.RuleOptions{VerifySCT: &falseVar},
			false,
			true,
			"",
			"",
			nil,
			nil,
		},
		{ // 6: rekor and ct log pub keys
			"11_keyless",
			policy.RuleOptions{},
			false,
			false,
			"",
			"",
			map[string]int64{
				"c0d23d6ad406973f9559f3ba2d1ca01f84147d8ffc5b8445c224f98b9591801d": 3252071251971923621,
			},
			map[string]int64{
				"dd3d306ac6c7113263191e1c99673702a24a5eb8de3cadff878a72802f29ee8e": -7745516234792056340,
			},
		},
	}

	mock_remote, remote_ctrl := testhelper.MockRemote()
	defer mock_remote.Close()
	mock_remote_host := strings.TrimPrefix(mock_remote.URL, "http://")

	for idx, tc := range testCases {
		var validator CosignValidator
		ctx := context.Background()
		img, err := image.New(fmt.Sprintf("%s/%s", mock_remote_host, "image"))
		assert.Nil(t, err, "test case %d: image should be valid", idx+1)
		cvBytes, err := os.ReadFile(PRE + tc.file + ".yaml")
		assert.Nil(t, err, "test case %d: config should be valid", idx+1)
		err = yaml.Unmarshal(cvBytes, &validator)
		assert.Nil(t, err, "test case %d: validator should be valid", idx+1)

		if len(validator.Auth.AuthConfigs) > 0 {
			for _, authConfig := range validator.Auth.AuthConfigs {
				validator.Auth.AuthConfigs[mock_remote_host] = authConfig
				break
			}
		}

		opts, _ := validator.setupOptions(ctx, tc.opts, img)
		assert.Equal(t, tc.expIgnoreTlog, opts.IgnoreTlog, idx+1)
		assert.Equal(t, tc.expIgnoreSCT, opts.IgnoreSCT, idx+1)

		remote.DigestTag(img, opts.RegistryClientOpts...)
		assert.Equal(t, tc.expUser, remote_ctrl.Username, idx+1)
		assert.Equal(t, tc.expPass, remote_ctrl.Password, idx+1)

		if tc.expRekorKeys != nil {
			for key, value := range opts.RekorPubKeys.Keys {
				assert.Contains(t, tc.expRekorKeys, key, idx+1)
				assert.Equal(t, tc.expRekorKeys[key], value.PubKey.(*ecdsa.PublicKey).X.Int64(), idx+1)
			}
		}

		if tc.expCTLogKeys != nil {
			for key, value := range opts.CTLogPubKeys.Keys {
				assert.Contains(t, tc.expCTLogKeys, key, idx+1)
				assert.Equal(t, tc.expCTLogKeys[key], value.PubKey.(*ecdsa.PublicKey).X.Int64(), idx+1)
			}
		}
	}
}

func TestValidateImage(t *testing.T) {
	var falseVar bool = false
	var testCases = []struct {
		file   string
		image  string
		args   policy.RuleOptions
		digest string
		err    string
	}{
		{ // 1: working case
			"01_cosign",
			"securesystemsengineering/testimage:multi-cosigned-alice",
			policy.RuleOptions{TrustRoot: "alice", VerifyTLog: &falseVar},
			"sha256:071bf7a986f1ca9cb2a1f0bc8392822a7777f90d58f2d2c6f271913e08de7c81",
			"",
		},
		{ // 2: unknown trustRoot
			"01_cosign",
			"image",
			policy.RuleOptions{TrustRoot: "charlie"},
			"",
			"error getting verifiers",
		},
		{ // 3: unmet threshold
			"01_cosign",
			"securesystemsengineering/testimage:co-unsigned",
			policy.RuleOptions{TrustRoot: "*", VerifyTLog: &falseVar},
			"",
			"validation threshold not reached",
		},
		{ // 4: non-existant image
			"01_cosign",
			"securesystemsengineering/testimage:co-nonexistent",
			policy.RuleOptions{TrustRoot: "*", VerifyTLog: &falseVar},
			"",
			"securesystemsengineering/testimage:co-nonexistent does not exist",
		},
		{ // 5: working multi signature case
			"01_cosign",
			"securesystemsengineering/testimage:multi-cosigned-alice-bob-charlie",
			policy.RuleOptions{TrustRoot: "*", Threshold: 2, VerifyTLog: &falseVar},
			"sha256:bfec161fecb0a887df7cb85e4da327c65986ccda7060cf3cd92171c6c90d7533",
			"",
		},
		{ // 6: multi signature threshold not reached
			"01_cosign",
			"securesystemsengineering/testimage:multi-cosigned-alice-bob-charlie",
			policy.RuleOptions{TrustRoot: "*", Threshold: 3, VerifyTLog: &falseVar},
			"",
			"validation threshold not reached",
		},
		{ // 7: missing required signature
			"01_cosign",
			"securesystemsengineering/testimage:multi-cosigned-alice",
			policy.RuleOptions{
				TrustRoot:  "*",
				Required:   []string{"bob"},
				VerifyTLog: &falseVar,
			},
			"",
			"missing required signatures from [bob]",
		},
		{ // 8: missing required signature
			"01_cosign",
			"securesystemsengineering/testimage:multi-cosigned-alice",
			policy.RuleOptions{
				TrustRoot:  "*",
				Required:   []string{"bob", "alice"},
				VerifyTLog: &falseVar,
			},
			"",
			"missing required signatures from [bob]",
		},
		{ // 9: no signature present
			"01_cosign",
			"securesystemsengineering/testimage:co-unsigned",
			policy.RuleOptions{TrustRoot: "alice", VerifyTLog: &falseVar},
			"",
			"no signatures found",
		},
		// { // 10: missing tlog entry
		// 	"01_cosign",
		// 	"securesystemsengineering/testimage:multi-cosigned-alice",
		// 	policy.RuleOptions{TrustRoot: "alice"},
		// 	"",
		// 	"no signed digests",
		// },
	}

	reg := testhelper.MockRegistry(PRE)
	defer reg.Close()

	for idx, tc := range testCases {
		var cv CosignValidator
		ctx := context.Background()
		cvBytes, _ := os.ReadFile(PRE + tc.file + ".yaml")
		err := yaml.Unmarshal(cvBytes, &cv)
		assert.Nil(t, err, idx+1)

		img, err := image.New(strings.TrimPrefix(reg.URL, "http://") + "/" + tc.image)
		assert.NoError(t, err, idx+1)

		digest, err := cv.ValidateImage(ctx, img, tc.args)

		if tc.err != "" {
			assert.Error(t, err, idx+1)
			assert.ErrorContains(t, err, tc.err, idx+1)
		} else {
			assert.NoError(t, err)
			assert.Equal(t, tc.digest, digest)
		}
	}
}

func TestValidateImageKeyless(t *testing.T) {
	var testCases = []struct {
		config string
		image  string
		args   policy.RuleOptions
		err    string
	}{
		{ // 1: working case
			"11_keyless",
			"securesystemsengineering/testimage:keyless",
			policy.RuleOptions{TrustRoot: "philipp-keyless"},
			"",
		},
		{ // 2: wrong subject / issuer
			"11_keyless",
			"securesystemsengineering/testimage:keyless",
			policy.RuleOptions{TrustRoot: "bob-keyless"},
			"none of the expected identities matched",
		},
	}

	reg := testhelper.MockRegistry(PRE)
	defer reg.Close()

	for idx, tc := range testCases {
		var cv CosignValidator
		ctx := context.Background()
		cvBytes, _ := os.ReadFile(PRE + tc.config + ".yaml")
		err := yaml.Unmarshal(cvBytes, &cv)
		assert.Nil(t, err, idx+1)

		img, err := image.New(strings.TrimPrefix(reg.URL, "http://") + "/" + tc.image)
		assert.NoError(t, err, idx+1)

		_, err = cv.ValidateImage(ctx, img, tc.args)

		if tc.err != "" {
			assert.Error(t, err, idx+1)
			assert.ErrorContains(t, err, tc.err, idx+1)
		} else {
			assert.NoError(t, err, idx+1)
		}
	}
}
