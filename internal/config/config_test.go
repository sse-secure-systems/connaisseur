package config

import (
	"connaisseur/internal/image"
	"connaisseur/internal/policy"
	"connaisseur/internal/validator"
	"connaisseur/internal/validator/auth"
	"connaisseur/internal/validator/cosignvalidator"
	"connaisseur/internal/validator/notaryv1"
	static "connaisseur/internal/validator/staticvalidator"
	"io"
	"os"
	"testing"

	"github.com/sirupsen/logrus"
	"github.com/stretchr/testify/assert"
)

const PRE string = "../../test/testdata/config/"

// to supress logging
func TestMain(m *testing.M) {
	logrus.SetOutput(io.Discard)
	os.Exit(m.Run())
}

func TestLoad(t *testing.T) {
	cfg, err := Load(PRE, "00_sample.yaml")

	assert.Nil(t, err)
	assert.NotEqual(t, &Config{}, cfg)

	assert.Equal(t, 3, len(cfg.Validators))
	assert.Equal(t, 11, len(cfg.Rules))
	assert.Equal(t, 2, len(cfg.Alerting.AdmitRequests.Receivers))
	assert.Equal(t, 1, len(cfg.Alerting.RejectRequests.Receivers))
}

func TestLoadError(t *testing.T) {
	var testCases = []struct {
		file     string
		errorMsg string
	}{
		{"01_val_no_name.yaml", "validator is missing a name"},
		{"02_val_no_type.yaml", "validator is missing a type"},
		{"03_unsupported_type.yaml", "unsupported type \"stati\" for validator"},
		{"04_unmarshal_cosign_error.yaml", "cannot unmarshal"},
		{"05_invalid_cosign.yaml", "unable to create Rekor client"},
		{"06_unmarshal_static_error.yaml", "cannot unmarshal"},
		{"07_invalid_validator.yaml", "cannot unmarshal"},
		{"08_unknown_field.yaml", "field invalid not found in type staticvalidator"},
		{"XX_no_file.yaml", "error sanitizing file with"},
	}

	for idx, tc := range testCases {
		_, err := Load(PRE, tc.file)

		assert.NotNil(t, err)
		assert.ErrorContainsf(t, err, tc.errorMsg, "test case %d", idx+1)
	}
}

func TestValidator(t *testing.T) {
	cfg, _ := Load(PRE, "00_sample.yaml")

	v1, _ := cfg.Validator("")
	assert.Equal(t, "default", v1.Name)
	assert.Equal(t, "static", v1.Type)
	assert.True(t, v1.SpecificValidator.(*static.StaticValidator).Approve)

	v2, _ := cfg.Validator("cosign")
	assert.Equal(t, "cosign", v2.Name)
	assert.Equal(t, "cosign", v2.Type)

	v3, err := cfg.Validator("none")
	assert.Nil(t, v3)
	assert.NotNil(t, err)
	assert.ErrorContains(t, err, "validator \"none\" not found")
}

func TestMatchingRule(t *testing.T) {
	cfg, _ := Load(PRE, "00_sample.yaml")

	var testCases = []struct {
		image   string
		pattern string
	}{
		{"image:tag", "docker.io/*:*"},
		{"registry.io/image:tag", "*:*"},
		{"registry.k8s.io/image", "registry.k8s.io/*:*"},
		{"image", "docker.io/*:*"},
		{
			"docker.io/securesystemsengineering/sample:v1",
			"docker.io/securesystemsengineering/sample:v1",
		},
		{
			"docker.io/securesystemsengineering/sample:v2",
			"docker.io/securesystemsengineering/sample",
		},
		{"my.registry/test:tag", "my.registry/test"},
		{"my.registry/abc:tag", "my.registry/*"},
		// {"docker.io/test:tag", "docker.io/test:*"}, // TODO: #1517
	}

	for idx, tc := range testCases {
		img, _ := image.New(tc.image)
		rule, _ := cfg.MatchingRule(img.Name())
		assert.Equalf(t, tc.pattern, rule.Pattern, "test case %d", idx+1)
	}

	_, err := cfg.MatchingRule("")
	assert.NotNil(t, err)
	assert.ErrorContains(t, err, "no matching rule")
}

func TestValidate(t *testing.T) {
	falseVar := false
	var testCfgs = []Config{
		{ // 1: static validator
			Validators: []validator.Validator{
				{
					Name: "valName",
					Type: "static",
					SpecificValidator: static.StaticValidator{
						Name:    "valName",
						Type:    "static",
						Approve: false,
					},
				},
			},
			Rules: []policy.Rule{
				{
					Pattern:   "somePattern",
					Validator: "valName",
					With: policy.RuleOptions{
						ValidationMode: "mutate",
					},
				},
			},
		},
		{ // 2: notaryv1 validator
			Validators: []validator.Validator{
				{
					Name: "valName",
					Type: "notaryv1",
					SpecificValidator: &notaryv1.NotaryV1Validator{
						Name: "valName",
						Type: "notaryv1",
						Host: "https://notary.docker.io",
						Cert: "someCert",
						Auth: auth.Auth{
							AuthConfigs: map[string]auth.AuthEntry{
								"notary.docker.io": {Username: "user", Password: "pass"},
								"example.com":      {Username: "user2", Password: "pass2"},
							},
							UseKeychain: false,
						},
						TrustRoots: []auth.TrustRoot{
							{Name: "alice", Key: "someKey"},
							{Name: "docker", Key: "someOtherKey"},
						},
					},
				},
			},
			Rules: []policy.Rule{
				{
					Pattern:   "somePattern",
					Validator: "valName",
					With: policy.RuleOptions{
						TrustRoot:      "*",
						Delegations:    []string{"alice", "bob"},
						VerifyTLog:     &falseVar,
						ValidationMode: "insecureValidateOnly",
					},
				},
			},
		},
		{ // 3: cosign validator
			Validators: []validator.Validator{
				{
					Name: "valName",
					Type: "cosign",
					SpecificValidator: &cosignvalidator.CosignValidator{
						Name: "valName",
						Type: "cosign",
						TrustRoots: []auth.TrustRoot{
							{Name: "trName", Key: "someKey"},
						},
					},
				},
			},
			Rules: []policy.Rule{
				{
					Pattern:   "somePattern",
					Validator: "valName",
					With: policy.RuleOptions{
						TrustRoot: "trustRoot",
						Threshold: 7,
						Required:  []string{"alice", "bob"},
					},
				},
			},
		},
		{ // 4: empty fields in policy rule
			Validators: []validator.Validator{
				{
					Name: "valName",
					Type: "static",
					SpecificValidator: static.StaticValidator{
						Name:    "valName",
						Type:    "static",
						Approve: false,
					},
				},
			},
			Rules: []policy.Rule{
				{
					Pattern:   "somePattern",
					Validator: "",
					With: policy.RuleOptions{
						VerifyTLog:     nil,
						ValidationMode: "",
					},
				},
			},
		},
	}
	for idx, cfg := range testCfgs {
		err := cfg.validate()
		assert.Nil(t, err, idx+1)
	}
}

func TestValidateErrors(t *testing.T) {
	falseVar := false
	var testCases = []struct {
		cfg Config
		err string
	}{
		{ // 1: needs at least one validator
			Config{},
			"Validators must contain at least 1 item",
		},
		{ // 2: needs at least one rule
			Config{},
			"Rules must contain at least 1 item",
		},
		{ // 3: valdator needs name
			Config{
				Validators: []validator.Validator{
					{
						Name: "",
						Type: "static",
						SpecificValidator: static.StaticValidator{
							Name:    "valName",
							Type:    "static",
							Approve: false,
						},
					},
				},
				Rules: []policy.Rule{
					{
						Pattern:   "somePattern",
						Validator: "valName",
						With: policy.RuleOptions{
							VerifyTLog:     &falseVar,
							ValidationMode: "mutate",
						},
					},
				},
			},
			"Name is a required field",
		},
		{ // 4: there's only some hard-coded validator types
			Config{
				Validators: []validator.Validator{
					{
						Name: "valName",
						Type: "something",
						SpecificValidator: static.StaticValidator{
							Name:    "valName",
							Type:    "static",
							Approve: false,
						},
					},
				},
				Rules: []policy.Rule{
					{
						Pattern:   "somePattern",
						Validator: "valName",
						With: policy.RuleOptions{
							VerifyTLog:     &falseVar,
							ValidationMode: "mutate",
						},
					},
				},
			},
			"Type must be one of [static notaryv1 cosign notation]",
		},
		{ // 5: validator type matches its Type field
			Config{
				Validators: []validator.Validator{
					{
						Name: "valName",
						Type: "static",
						SpecificValidator: static.StaticValidator{
							Name:    "valName",
							Type:    "cosign",
							Approve: false,
						},
					},
				},
				Rules: []policy.Rule{
					{
						Pattern:   "somePattern",
						Validator: "valName",
						With: policy.RuleOptions{
							VerifyTLog:     &falseVar,
							ValidationMode: "mutate",
						},
					},
				},
			},
			"Type is not equal to static",
		},
		{ // 6: nested validator needs name
			Config{
				Validators: []validator.Validator{
					{
						Name: "valName",
						Type: "static",
						SpecificValidator: static.StaticValidator{
							Name:    "",
							Type:    "static",
							Approve: false,
						},
					},
				},
				Rules: []policy.Rule{
					{
						Pattern:   "somePattern",
						Validator: "valName",
						With: policy.RuleOptions{
							VerifyTLog:     &falseVar,
							ValidationMode: "mutate",
						},
					},
				},
			},
			"Name is a required field",
		},
		{ // 7: each validator needs a specificValidator inside
			Config{
				Validators: []validator.Validator{
					{
						Name: "valName",
						Type: "static",
					},
				},
				Rules: []policy.Rule{
					{
						Pattern:   "somePattern",
						Validator: "valName",
						With: policy.RuleOptions{
							VerifyTLog:     &falseVar,
							ValidationMode: "mutate",
						},
					},
				},
			},
			"SpecificValidator is a required field",
		},
		{ // 8: rule needs pattern
			Config{
				Validators: []validator.Validator{
					{
						Name: "valName",
						Type: "static",
						SpecificValidator: static.StaticValidator{
							Name:    "",
							Type:    "static",
							Approve: false,
						},
					},
				},
				Rules: []policy.Rule{
					{
						Pattern:   "",
						Validator: "valName",
						With: policy.RuleOptions{
							VerifyTLog:     &falseVar,
							ValidationMode: "mutate",
						},
					},
				},
			},
			"Pattern is a required field",
		},
		{ // 9: no mismatch between validator and specific validator allowed
			Config{
				Validators: []validator.Validator{
					{
						Name: "valName",
						Type: "cosign",
						SpecificValidator: static.StaticValidator{
							Name:    "valName",
							Type:    "static",
							Approve: false,
						},
					},
				},
				Rules: []policy.Rule{
					{
						Pattern:   "somePattern",
						Validator: "valName",
						With: policy.RuleOptions{
							VerifyTLog: &falseVar,
						},
					},
				},
			},
			"Type must be equal to SpecificValidator.Type",
		},
		{ // 10: not required and delegations set at the same time
			Config{
				Validators: []validator.Validator{
					{
						Name: "valName",
						Type: "static",
						SpecificValidator: static.StaticValidator{
							Name:    "valName",
							Type:    "static",
							Approve: false,
						},
					},
				},
				Rules: []policy.Rule{
					{
						Pattern:   "somePattern",
						Validator: "valName",
						With: policy.RuleOptions{
							TrustRoot:      "trustRoot",
							VerifyTLog:     &falseVar,
							Threshold:      7,
							Required:       []string{"alice", "bob"},
							Delegations:    []string{"charlie", "dave"},
							ValidationMode: "mutate",
						},
					},
				},
			},
			"Required must not be set if Delegations is",
		},
		{ // 11: one of key or cert is required in trust root
			Config{
				Validators: []validator.Validator{
					{
						Name: "valName",
						Type: "notaryv1",
						SpecificValidator: &notaryv1.NotaryV1Validator{
							Name: "valName",
							Type: "notaryv1",
							Host: "https://notary.docker.io",
							TrustRoots: []auth.TrustRoot{
								{Name: "alice"},
							},
						},
					},
				},
				Rules: []policy.Rule{
					{
						Pattern:   "somePattern",
						Validator: "valName",
						With: policy.RuleOptions{
							VerifyTLog: &falseVar,
						},
					},
				},
			},
			"Key must be set if [Cert Keyless] isn't",
		},
		{ // 12: keyless need either issuer or issuer regex
			Config{
				Validators: []validator.Validator{
					{
						Name: "valName",
						Type: "cosign",
						SpecificValidator: &cosignvalidator.CosignValidator{
							Name: "valName",
							Type: "cosign",
							TrustRoots: []auth.TrustRoot{
								{Name: "trName", Keyless: auth.Keyless{
									Subject:     "subject",
									Issuer:      "issuer",
									IssuerRegex: "issuerRegex",
								}},
							},
						},
					},
				},
				Rules: []policy.Rule{
					{
						Pattern:   "somePattern",
						Validator: "valName",
						With:      policy.RuleOptions{},
					},
				},
			},
			"Issuer must not be set if IssuerRegex is",
		},
		{ // 13: Verification level
			Config{
				Validators: []validator.Validator{
					{
						Name: "valName",
						Type: "static",
						SpecificValidator: static.StaticValidator{
							Name:    "valName",
							Type:    "static",
							Approve: false,
						},
					},
				},
				Rules: []policy.Rule{
					{
						Pattern:   "somePattern",
						Validator: "valName",
						With: policy.RuleOptions{
							VerificationLevel: "invalid",
						},
					},
				},
			},
			"VerificationLevel must be one of [strict permissive audit]",
		},
	}
	for idx, tc := range testCases {
		err := tc.cfg.validate()
		assert.ErrorContains(t, err, tc.err, idx+1)
	}
}
