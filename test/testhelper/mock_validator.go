package testhelper

import (
	"connaisseur/internal/image"
	"connaisseur/internal/policy"
	"context"
	"fmt"
)

type MockValidator struct {
	Name string `yaml:"name"`
	Type string `yaml:"type"`
}

func (mv MockValidator) ValidateImage(
	_ context.Context,
	image *image.Image,
	_ policy.RuleOptions,
) (string, error) {
	switch image.OriginalString() {
	case "securesystemsengineering/alice-image:test":
		return "sha256:1234567890123456123456789012345612345678901234561234567890123456", nil
	case "busybox":
		return "", fmt.Errorf(
			"unabled to find signed digest for image docker.io/library/busybox:latest",
		)
	case "securesystemsengineering/alice-image@sha256:1234567890123456123456789012345612345678901234561234567890123456":
		return "sha256:1234567890123456123456789012345612345678901234561234567890123456", nil
	case "securesystemsengineering/alice-image:test@sha256:1234567890123456123456789012345612345678901234561234567890123456":
		return "sha256:1234567890123456123456789012345612345678901234561234567890123456", nil
	case "invalid-digest":
		return "sha256:123", nil
	default:
		return "", fmt.Errorf("unknown image %s", image.OriginalString())
	}
}

type MockAllowValidator struct {
	Name string `yaml:"name"`
	Type string `yaml:"type"`
}

func (mav MockAllowValidator) ValidateImage(
	_ context.Context,
	image *image.Image,
	_ policy.RuleOptions,
) (string, error) {
	return "sha256:1234567890123456123456789012345612345678901234561234567890123456", nil
}

type MockDenyValidator struct {
	Name string `yaml:"name"`
	Type string `yaml:"type"`
}

func (mdv MockDenyValidator) ValidateImage(
	_ context.Context,
	image *image.Image,
	_ policy.RuleOptions,
) (string, error) {
	return "", fmt.Errorf("mock validation failure")
}
