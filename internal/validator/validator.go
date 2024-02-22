package validator

import (
	"connaisseur/internal/constants"
	"connaisseur/internal/image"
	"connaisseur/internal/policy"
	cosign "connaisseur/internal/validator/cosignvalidator"
	nv1 "connaisseur/internal/validator/notaryv1"
	static "connaisseur/internal/validator/staticvalidator"
	"context"
	"fmt"
)

type Validator struct {
	// Name of the validator
	Name string `validate:"required,eqcsfield=SpecificValidator.Name"`
	// Type of the validator
	Type string `validate:"oneof=static notaryv1 cosign,eqcsfield=SpecificValidator.Type"`
	// the specific validator (e.g. cosign, static)
	SpecificValidator SpecificValidator `validate:"required"`
	Validate
}

type SpecificValidator interface {
	// implements Validate interface
	Validate
}

type Validate interface {
	ValidateImage(context.Context, *image.Image, policy.RuleOptions) (string, error)
}

// UnmarshalYAML implements the yaml.Unmarshaler interface
// for the Validator struct. It sets the Name and Type
// fields and based on the Type, it loads the specific
// validator.
func (v *Validator) UnmarshalYAML(unmarshal func(interface{}) error) error {
	var vData map[string]interface{}
	if err := unmarshal(&vData); err != nil {
		return err
	}

	// 2 required fields for each validator: name and type
	name, ok := vData["name"]
	if !ok {
		return fmt.Errorf("validator is missing a name")
	}
	v.Name = name.(string)

	type_, ok := vData["type"]
	if !ok {
		return fmt.Errorf("validator is missing a type")
	}
	v.Type = type_.(string)

	// based on type, additional required attribute
	// might exist
	var specific SpecificValidator
	switch v.Type {
	case constants.StaticValidator:
		specific = &static.StaticValidator{}
	case constants.CosignValidator:
		specific = &cosign.CosignValidator{}
	case constants.NotaryV1Validator:
		specific = &nv1.NotaryV1Validator{}
	default:
		return fmt.Errorf("unsupported type \"%s\" for validator", v.Type)
	}

	// load attributes and validate them
	if err := unmarshal(specific); err != nil {
		return err
	}

	v.SpecificValidator = specific

	return nil
}

// uses the specific validator to validate the image
func (v *Validator) ValidateImage(
	ctx context.Context,
	img *image.Image,
	opts policy.RuleOptions,
) (string, error) {
	return v.SpecificValidator.ValidateImage(ctx, img, opts)
}
