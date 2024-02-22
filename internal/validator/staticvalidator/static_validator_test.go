package staticvalidator

import (
	"connaisseur/internal/image"
	"connaisseur/internal/policy"
	"context"
	"testing"

	"github.com/stretchr/testify/assert"
)

func TestValidateImage(t *testing.T) {
	var testCases = []struct {
		image   string
		approve bool
		digest  string
		err     bool
	}{
		{
			"test-image",
			true,
			"",
			false,
		},
		{
			"test-image",
			false,
			"",
			true,
		},
		{
			"test-image:latest",
			true,
			"",
			false,
		},
		{
			"test-image@sha256:91ac9b26df583762234c1cdb2fc930364754ccc59bc752a2bfe298d2ea68f9ff",
			true,
			"sha256:91ac9b26df583762234c1cdb2fc930364754ccc59bc752a2bfe298d2ea68f9ff",
			false,
		},
	}

	for idx, tc := range testCases {
		sv := StaticValidator{
			Approve: tc.approve,
		}

		img, _ := image.New(tc.image)
		digest, err := sv.ValidateImage(context.TODO(), img, policy.RuleOptions{})
		if tc.err {
			assert.NotNilf(t, err, "test case %d", idx+1)
		} else {
			assert.Nilf(t, err, "test case %d", idx+1)
		}
		assert.Equalf(t, tc.digest, digest, "test case %d", idx+1)
	}
}
