package utils

import (
	"connaisseur/internal/constants"
	"testing"

	"github.com/stretchr/testify/assert"
)

func TestFeatureFlag(t *testing.T) {
	t.Setenv("FEATURE_TRUE", "true")
	t.Setenv("FEATURE_FALSE", "false")

	assert.True(t, FeatureFlagOn("FEATURE_TRUE"))
	assert.False(t, FeatureFlagOn("FEATURE_FALSE"))
}

func TestFeatureFlagNotSet(t *testing.T) {
	assert.False(t, FeatureFlagOn("FEATURE_NOT_SET"))
}

func TestFeatureFlagWrongFormat(t *testing.T) {
	t.Setenv("FEATURE_WRONG_FORMAT", "this isn't a boolean")

	assert.False(t, FeatureFlagOn("FEATURE_WRONG_FORMAT"))
}

func TestFeatureFlagDefaultValues(t *testing.T) {
	t.Setenv(constants.AutomaticChildApproval, "this isn't a boolean")
	t.Setenv(constants.AutomaticUnchangedApproval, "this isn't a boolean")
	t.Setenv(constants.DetectionMode, "this isn't a boolean")

	assert.True(t, FeatureFlagOn(constants.AutomaticChildApproval))
	assert.False(t, FeatureFlagOn(constants.AutomaticUnchangedApproval))
	assert.False(t, FeatureFlagOn(constants.DetectionMode))

}

func TestBlockAllResources(t *testing.T) {
	var testCases = []struct {
		rvm string
		exp bool
	}{
		{
			rvm: "All",
			exp: true,
		},
		{
			rvm: "all",
			exp: true,
		},
		{
			rvm: "podsOnly",
			exp: false,
		},
		{
			rvm: "PodsOnly",
			exp: false,
		},
		{
			rvm: "somethingDifferent",
			exp: true,
		},
	}

	for _, tc := range testCases {
		t.Setenv(constants.ResourceValidationMode, tc.rvm)
		assert.Equal(t, tc.exp, BlockAllResources())
	}
}
