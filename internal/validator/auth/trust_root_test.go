package auth

import (
	"testing"

	"github.com/stretchr/testify/assert"
)

func TestGetTrustRoots(t *testing.T) {
	emptyKeyless := Keyless{}
	a := TrustRoot{"a", "a", "", "", emptyKeyless}
	b := TrustRoot{"b", "b", "", "", emptyKeyless}
	c := TrustRoot{"c", "c", "", "", emptyKeyless}
	defaultRoot := TrustRoot{"default", "default", "", "", emptyKeyless}

	var testCases = []struct {
		keyRefs      []string
		trustRoots   []TrustRoot
		defaultValue bool
		expected     []TrustRoot
		expectedErr  string
	}{
		{
			[]string{"a"},
			[]TrustRoot{a, b},
			false,
			[]TrustRoot{a},
			"",
		},
		{
			[]string{"a", "c"},
			[]TrustRoot{a, b, c},
			false,
			[]TrustRoot{a, c},
			"",
		},
		{
			[]string{"*"},
			[]TrustRoot{a, b, c},
			false,
			[]TrustRoot{a, b, c},
			"",
		},
		{
			[]string{"a"},
			[]TrustRoot{a, defaultRoot},
			true,
			[]TrustRoot{a},
			"",
		},
		{
			[]string{},
			[]TrustRoot{a, defaultRoot},
			true,
			[]TrustRoot{defaultRoot},
			"",
		},
		{
			nil,
			[]TrustRoot{a, defaultRoot},
			true,
			[]TrustRoot{defaultRoot},
			"",
		},
		{
			[]string{"c"},
			[]TrustRoot{a, defaultRoot},
			true,
			nil,
			"unable to find trust root c",
		},
		{
			[]string{},
			[]TrustRoot{a, b},
			false,
			nil,
			"no trust roots defined for key references",
		},
		{
			[]string{""},
			[]TrustRoot{a, defaultRoot},
			true,
			[]TrustRoot{defaultRoot},
			"",
		},
		{
			[]string{""},
			[]TrustRoot{a, b},
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
