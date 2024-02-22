package cosignvalidator

import (
	"connaisseur/internal/constants"
	"connaisseur/internal/image"
	"connaisseur/internal/policy"
	"context"
	"crypto/ecdsa"
	"fmt"
	"io"
	"os"
	"testing"

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
		rekor      string
		trustRoots []string
		err        string
	}{
		{
			"01_cosign",
			"default",
			"",
			[]string{"alice", "bob"},
			"",
		},
		{
			"02_rekor",
			"rekor",
			"https://definitely-not-rekor.sigstore.dev",
			[]string{"default"},
			"",
		},
		{
			"03_unmarshal_err",
			"",
			"",
			[]string{},
			"yaml: unmarshal errors",
		},
		{
			"04_rekor_err",
			"",
			"",
			[]string{},
			"invalid url for rekor",
		},
		{
			"05_no_trust_roots",
			"",
			"",
			[]string{},
			"no trust roots provided for validator",
		},
		{
			"10_invalid_cert",
			"",
			"",
			[]string{},
			"invalid certificate",
		},
	}

	for _, tc := range testCases {
		var cv CosignValidator

		cvBytes, _ := os.ReadFile(PRE + tc.file + ".yaml")
		err := yaml.Unmarshal(cvBytes, &cv)

		if tc.err != "" {
			assert.NotNil(t, err)
			assert.ErrorContains(t, err, tc.err)
		} else {
			assert.Nil(t, err)
			assert.Equal(t, tc.name, cv.Name)
			if tc.rekor != "" {
				assert.Equal(t, tc.rekor, cv.Rekor)
			} else {
				assert.Equal(t, constants.DefaultRekorHost, cv.Rekor)
			}
			for i, tr := range tc.trustRoots {
				assert.Contains(t, tr, cv.TrustRoots[i].Name)
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
				pubKey, _ := verifier.Verifier.PublicKey()
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
		expPubKeys    []int64
		expIgnoreTLog bool
		expErr        string
	}{
		{
			"01_cosign",
			policy.RuleOptions{TrustRoot: "bob"},
			[]int64{-7384356341354458600},
			false,
			"",
		},
		{
			"06_auth",
			policy.RuleOptions{TrustRoot: "alice"},
			[]int64{-3916471775317094451},
			false,
			"",
		},
		{ // Specifying VerifyTLog as default work
			"06_auth",
			policy.RuleOptions{TrustRoot: "alice", VerifyTLog: &trueVar},
			[]int64{-3916471775317094451},
			false,
			"",
		},
		{ // Specifying VerifyTLog with non-default value changes outcome
			"06_auth",
			policy.RuleOptions{TrustRoot: "alice", VerifyTLog: &falseVar},
			[]int64{-3916471775317094451},
			true,
			"",
		},
		{
			"07_keychain",
			policy.RuleOptions{TrustRoot: "alice"},
			[]int64{-3916471775317094451},
			false,
			"",
		},
		{
			"08_cert",
			policy.RuleOptions{TrustRoot: "alice"},
			[]int64{-3916471775317094451},
			false,
			"",
		},
		{
			"09_full_config",
			policy.RuleOptions{TrustRoot: "*"},
			[]int64{-3916471775317094451, -7384356341354458600, -7401950337678553810},
			false,
			"",
		},
		{ // Missing verifier
			"01_cosign",
			policy.RuleOptions{TrustRoot: "charlie"},
			[]int64{},
			false,
			"error getting verifier",
		},
	}

	for idx, tc := range testCases {
		var validator CosignValidator
		ctx := context.Background()
		img, _ := image.New("test")
		cvBytes, err := os.ReadFile(PRE + tc.file + ".yaml")
		assert.Nil(t, err, "test case %d: config should be valid", idx+1)
		err = yaml.Unmarshal(cvBytes, &validator)
		assert.Nil(t, err, "test case %d: validator should be valid", idx+1)
		verifiers, err := validator.verifiers(ctx, []string{tc.opts.TrustRoot})
		// In case there's an expected error, verifiers may be nil, otherwise they should be valid
		if err != nil && tc.expErr == "" {
			assert.True(t, false, "test case %d: verifiers should be valid", idx+1)
		}

		// If there's no  error, the should be as many verifiers as expected public keys
		if tc.expErr == "" {
			assert.Equal(t, len(tc.expPubKeys), len(verifiers), "test case %d", idx+1)
		}

		verifierPubKeys := []int64{}
		for _, verifier := range verifiers {
			opts, err := validator.setupOptions(ctx, tc.opts, img, verifier.Verifier)

			if tc.expErr != "" {
				assert.NotNil(t, err, "test case %d", idx+1)
				assert.ErrorContains(t, err, tc.expErr, "test case %d", idx+1)
			} else {
				pubKey, _ := opts.SigVerifier.PublicKey()
				verifierPubKeys = append(verifierPubKeys, pubKey.(*ecdsa.PublicKey).X.Int64())
				assert.Nil(t, err, "test case %d", idx+1)
				assert.Equal(t, tc.expIgnoreTLog, opts.IgnoreTlog, "test case %d", idx+1)
			}
		}
		assert.ElementsMatch(t, tc.expPubKeys, verifierPubKeys, "test case %d", idx+1)
	}
}

func TestSetupOptionsInvalidRekor(t *testing.T) {
	var validator CosignValidator
	ctx := context.Background()
	img, _ := image.New("test")
	cvBytes, err := os.ReadFile(PRE + "02_rekor.yaml")
	assert.Nil(t, err)
	err = yaml.Unmarshal(cvBytes, &validator)
	assert.Nil(t, err)
	validator.Rekor = "https://example.com/ invalid %U RL" // monkey-patch rekor URL as otherwise it can't be invalid
	verifiers, err := validator.verifiers(ctx, []string{})
	assert.Nil(t, err)
	opts := policy.RuleOptions{}
	_, err = validator.setupOptions(ctx, opts, img, verifiers[0].Verifier)
	assert.NotNil(t, err)
	assert.ErrorContains(t, err, "unable to create Rekor client")
}

func TestValidateImage(t *testing.T) {
	// falseVar := false
	var testCases = []struct {
		file   string
		image  string
		args   policy.RuleOptions
		digest string
		expErr string
	}{ // The underneath tests currently don't run offline and should stay commented out until we manage to resolve that issue. Also add positive test for signature that is in transparencyLog.
		// { // 1:
		// 	"01_cosign",
		// 	"securesystemsengineering/testimage:multi-cosigned-alice",
		// 	policy.RuleOptions{TrustRoot: "alice", VerifyTLog: &falseVar},
		// 	"sha256:071bf7a986f1ca9cb2a1f0bc8392822a7777f90d58f2d2c6f271913e08de7c81",
		// 	"",
		// },
		// { // 2:
		// 	"01_cosign",
		// 	"image",
		// 	policy.RuleOptions{TrustRoot: "charlie"},
		// 	"",
		// 	"error getting verifiers",
		// },
		// { // 3:
		// 	"01_cosign",
		// 	"securesystemsengineering/testimage:co-unsigned",
		// 	policy.RuleOptions{TrustRoot: "*"},
		// 	"",
		// 	"validation threshold not reached",
		// },
		// { // 4:
		// 	"01_cosign",
		// 	"securesystemsengineering/testimage:co-nonexistent",
		// 	policy.RuleOptions{TrustRoot: "*"},
		// 	"",
		// 	"image securesystemsengineering/testimage:co-nonexistent does not exist",
		// },
		// {
		// 	"01_cosign",
		// 	"securesystemsengineering/testimage:multi-cosigned-alice-bob-charlie",
		// 	policy.RuleOptions{TrustRoot: "*", Threshold: 2, VerifyTLog: &falseVar},
		// 	"sha256:bfec161fecb0a887df7cb85e4da327c65986ccda7060cf3cd92171c6c90d7533",
		// 	"",
		// },
		// { // 5:
		// 	"01_cosign",
		// 	"securesystemsengineering/testimage:multi-cosigned-alice-bob-charlie",
		// 	policy.RuleOptions{TrustRoot: "*", Threshold: 3, VerifyTLog: &falseVar},
		// 	"",
		// 	"validation threshold not reached",
		// },
		// { // 6:
		// 	"01_cosign",
		// 	"securesystemsengineering/testimage:multi-cosigned-alice",
		// 	policy.RuleOptions{
		// 		TrustRoot:  "*",
		// 		Required:   []string{"bob"},
		// 		VerifyTLog: &falseVar,
		// 	},
		// 	"",
		// 	"missing required signatures from [bob]",
		// },
		// { // 7:
		// 	"01_cosign",
		// 	"securesystemsengineering/testimage:multi-cosigned-alice",
		// 	policy.RuleOptions{
		// 		TrustRoot:  "*",
		// 		Required:   []string{"bob", "alice"},
		// 		VerifyTLog: &falseVar,
		// 	},
		// 	"",
		// 	"missing required signatures from [bob]",
		// },
		// { // 8:
		// 	"01_cosign",
		// 	"securesystemsengineering/testimage:co-unsigned",
		// 	policy.RuleOptions{TrustRoot: "alice", VerifyTLog: &falseVar},
		// 	"",
		// 	"no signed digests",
		// },
		// { // 9: missing tlog entry
		// 	"01_cosign",
		// 	"securesystemsengineering/testimage:multi-cosigned-alice",
		// 	policy.RuleOptions{TrustRoot: "alice"},
		// 	"",
		// 	"no signed digests",
		// },
	}
	for idx, tc := range testCases {
		tc := tc // needed due to for loop reusing variable
		t.Run(fmt.Sprintf("test case %d", idx+1), func(t *testing.T) {
			t.Parallel()

			var cv CosignValidator
			ctx := context.Background()
			cvBytes, _ := os.ReadFile(PRE + tc.file + ".yaml")
			err := yaml.Unmarshal(cvBytes, &cv)
			assert.Nil(t, err)

			img, _ := image.New(tc.image)
			digest, err := cv.ValidateImage(ctx, img, tc.args)

			if tc.expErr != "" {
				assert.NotNil(t, err)
				assert.ErrorContains(t, err, tc.expErr)
			} else {
				assert.Nil(t, err)
				assert.Equal(t, tc.digest, digest)
			}
		})
	}
}
