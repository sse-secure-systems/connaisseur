package validator

import (
	"connaisseur/internal/image"
	"connaisseur/internal/policy"
	"connaisseur/internal/validator/cosignvalidator"
	"connaisseur/internal/validator/notaryv1"
	"connaisseur/internal/validator/staticvalidator"
	"context"
	"os"
	"testing"

	"github.com/stretchr/testify/assert"
	"gopkg.in/yaml.v3"
)

const PRE string = "../../test/testdata/validators/"

func TestValidator(t *testing.T) {
	var testCases = []struct {
		validator string
		type_     string
	}{
		{
			"01_static",
			"static",
		},
		{
			"02_cosign",
			"cosign",
		},
		{
			"08_nv1",
			"notaryv1",
		},
	}

	for _, tc := range testCases {
		var val Validator

		valBytes, _ := os.ReadFile(PRE + tc.validator + ".yaml")
		err := yaml.Unmarshal(valBytes, &val)
		assert.Nil(t, err)

		assert.Equal(t, tc.type_, val.Type)
		switch val.Type {
		case "cosign":
			assert.IsType(t, &cosignvalidator.CosignValidator{}, val.SpecificValidator)
		case "static":
			assert.IsType(t, &staticvalidator.StaticValidator{}, val.SpecificValidator)
		case "notaryv1":
			assert.IsType(t, &notaryv1.NotaryV1Validator{}, val.SpecificValidator)
		}
	}
}

func TestValidatorError(t *testing.T) {
	var testCases = []struct {
		validator string
		errorMsg  string
	}{
		{
			"03_no_name",
			"validator is missing a name",
		},
		{
			"04_no_type",
			"validator is missing a type",
		},
		{
			"05_unsupported_type",
			"unsupported type \"stati\" for validator",
		},
		{
			"06_unmarshal_error",
			"no trust roots provided for validator default",
		},
		{
			"09_err_unmarshal",
			"cannot unmarshal !!seq into string",
		},
	}

	for idx, tc := range testCases {
		var val Validator

		valBytes, _ := os.ReadFile(PRE + tc.validator + ".yaml")
		err := yaml.Unmarshal(valBytes, &val)

		assert.NotNil(t, err)
		assert.ErrorContainsf(t, err, tc.errorMsg, "test case %d", idx+1)
	}
}

func TestValidateImage(t *testing.T) {
	ctx := context.Background()
	var val Validator

	valBytes, _ := os.ReadFile(PRE + "01_static.yaml")
	err := yaml.Unmarshal(valBytes, &val)
	assert.Nil(t, err)

	i, _ := image.New("test")
	img, err := val.ValidateImage(ctx, i, policy.RuleOptions{})
	assert.Nil(t, err)
	assert.Equal(t, "", img)
}
