package image

import (
	"testing"

	"github.com/stretchr/testify/assert"
)

func TestNewRegistryRepo(t *testing.T) {
	var testCases = []struct {
		input  string
		output string
		err    string
	}{
		{ // 1: valid registry and repo
			"registry.io/repo",
			"registry.io/repo",
			"",
		},
		{ // 2: valid registry and repo with subpath
			"registry.io/repo/sub",
			"registry.io/repo/sub",
			"",
		},
		{ // 3: valid registry and no repo
			"registry.io",
			"registry.io",
			"",
		},
		{ // 4: valid registry with trailing slash and no repo
			"registry.io/",
			"registry.io",
			"",
		},
		{ // 5: valid registry and repo with http prefix
			"https://registry.io/repo",
			"registry.io/repo",
			"",
		},
		{ // 6: invalid registry
			"[]\\/repo]",
			"",
			"unable to parse registry",
		},
		{ // 7: invalid repo
			"registry.io/[]\\/repo",
			"",
			"unable to parse repository",
		},
		{ // 8: docker io registry
			"http://index.docker.io/v1/",
			"index.docker.io",
			"",
		},
	}

	for idx, tc := range testCases {
		rr, err := NewRegistryRepo(tc.input)

		if tc.err != "" {
			assert.NotNil(t, err, idx+1)
			assert.ErrorContains(t, err, tc.err, idx+1)
		} else {
			assert.Nil(t, err, idx+1)
			assert.Equal(t, rr.String(), tc.output, idx+1)
		}
	}
}
