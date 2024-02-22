package staticvalidator

import (
	"connaisseur/internal/image"
	"connaisseur/internal/policy"
	"context"
	"fmt"
)

type StaticValidator struct {
	// name of the validator
	Name string `yaml:"name" validate:"required"`
	// type of the validator (will always be "static")
	Type string `yaml:"type" validate:"eq=static"`
	// approve or deny
	Approve bool `yaml:"approve"`
}

// validate an image by either approving or denying it
// based on the approve field
func (sv StaticValidator) ValidateImage(
	_ context.Context,
	img *image.Image,
	_ policy.RuleOptions,
) (string, error) {
	if sv.Approve {
		return img.Digest(), nil
	}
	return "", fmt.Errorf("static deny")
}
