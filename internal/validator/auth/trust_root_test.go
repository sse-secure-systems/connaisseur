package auth

import (
	"testing"

	"github.com/stretchr/testify/assert"
)

func TestGetTrustRoots(t *testing.T) {
	var testCases = []struct {
		keyRefs      []string
		trustRoots   []TrustRoot
		defaultValue bool
		expected     []TrustRoot
		expectedErr  string
	}{
		{
			[]string{"a"},
			[]TrustRoot{{"a", "a", ""}, {"b", "b", ""}},
			false,
			[]TrustRoot{{"a", "a", ""}},
			"",
		},
		{
			[]string{"a", "c"},
			[]TrustRoot{{"a", "a", ""}, {"b", "b", ""}, {"c", "c", ""}},
			false,
			[]TrustRoot{{"a", "a", ""}, {"c", "c", ""}},
			"",
		},
		{
			[]string{"*"},
			[]TrustRoot{{"a", "a", ""}, {"b", "b", ""}, {"c", "c", ""}},
			false,
			[]TrustRoot{{"a", "a", ""}, {"b", "b", ""}, {"c", "c", ""}},
			"",
		},
		{
			[]string{"a"},
			[]TrustRoot{{"a", "a", ""}, {"default", "default", ""}},
			true,
			[]TrustRoot{{"a", "a", ""}},
			"",
		},
		{
			[]string{},
			[]TrustRoot{{"a", "a", ""}, {"default", "default", ""}},
			true,
			[]TrustRoot{{"default", "default", ""}},
			"",
		},
		{
			nil,
			[]TrustRoot{{"a", "a", ""}, {"default", "default", ""}},
			true,
			[]TrustRoot{{"default", "default", ""}},
			"",
		},
		{
			[]string{"c"},
			[]TrustRoot{{"a", "a", ""}, {"default", "default", ""}},
			true,
			nil,
			"unable to find trust root c",
		},
		{
			[]string{},
			[]TrustRoot{{"a", "a", ""}, {"b", "b", ""}},
			false,
			nil,
			"no trust roots defined for key references",
		},
		{
			[]string{""},
			[]TrustRoot{{"a", "a", ""}, {"default", "default", ""}},
			true,
			[]TrustRoot{{"default", "default", ""}},
			"",
		},
		{
			[]string{""},
			[]TrustRoot{{"a", "a", ""}, {"b", "b", ""}},
			false,
			nil,
			"unable to find trust root",
		},
	}

	for _, tc := range testCases {
		actual, err := GetTrustRoots(tc.keyRefs, tc.trustRoots, tc.defaultValue)

		if tc.expectedErr != "" {
			assert.NotNil(t, err)
			assert.ErrorContains(t, err, tc.expectedErr)
		} else {
			assert.Nil(t, err)
			assert.Equal(t, len(tc.expected), len(actual))

			for idx, tr := range tc.expected {
				assert.Equal(t, tr.Name, actual[idx].Name)
				assert.Equal(t, tr.Key, actual[idx].Key)
			}
		}
	}
}
