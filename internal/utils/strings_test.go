package utils

import (
	"testing"

	"github.com/stretchr/testify/assert"
)

func TestLongestCommonPrefix(t *testing.T) {
	var testCases = []struct {
		strs []string
		lcp  string
	}{
		{
			[]string{"test-image"},
			"test-image",
		},
		{
			[]string{"test-image", "test-image"},
			"test-image",
		},
		{
			[]string{"test-image", "test-image:latest"},
			"test-image",
		},
		{
			[]string{"test-image", "test-image:latest", "test-image:1.0"},
			"test-image",
		},
		{
			[]string{"thequickbrownfox", "thequickbrownfoxjumpedoverthelazydog"},
			"thequickbrownfox",
		},
		{
			[]string{"thequickbrownfoxjumpedoverthelazydog", "thequickbrownfox"},
			"thequickbrownfox",
		},
		{
			[]string{"they", "have", "nothing", "in", "common"},
			"",
		},
	}

	for _, tc := range testCases {
		assert.Equal(t, tc.lcp, LongestCommonPrefix(tc.strs))
	}
}

func TestStringOverlap(t *testing.T) {
	var testCases = []struct {
		a, b, overlap string
	}{
		{
			"index.docker.io/library/test-image",
			"test-image",
			"test-image",
		},
		{
			"index.docker.io/library/test-image",
			"index.docker.io/library/test-image",
			"index.docker.io/library/test-image",
		},
		{
			"index.docker.io/library/test-image",
			"library/test-image",
			"library/test-image",
		},
		{
			"index.docker.io/library/test-image",
			"index.docker.io/library/test-image:latest",
			"index.docker.io/library/test-image",
		},
		{
			"index.docker.io/library/test-image",
			"nothing",
			"",
		},
	}

	for _, tc := range testCases {
		assert.Equal(t, tc.overlap, StringOverlap(tc.a, tc.b))
	}
}

func TestHasPrefixes(t *testing.T) {
	var testCases = []struct {
		s        string
		prefixes []string
		result   bool
	}{
		{
			"http://index.docker.io",
			[]string{"http://", "https://"},
			true,
		},
		{
			"https://index.docker.io",
			[]string{"http://", "https://"},
			true,
		},
		{
			"index.docker.io",
			[]string{"http://", "https://"},
			false,
		},
	}

	for _, tc := range testCases {
		assert.Equal(t, tc.result, HasPrefixes(tc.s, tc.prefixes...))
	}
}

func TestJsonEscapeString(t *testing.T) {
	var testCases = []struct {
		s, escaped string
	}{
		{ // 1: valid json
			"test",
			"test",
		},
		{ // 2: dangerous characters are escaped
			`test"test`,
			`test\"test`,
		},
		{ // 3: more dangerous characters are escaped
			`{"test": "more tests"}`,
			`{\"test\": \"more tests\"}`,
		},
		{ // 4: single quotes are not escaped
			`{'test': 'more tests'}`,
			`{'test': 'more tests'}`,
		},
	}

	for idx, tc := range testCases {
		result := JsonEscapeString(tc.s)

		assert.Equal(t, tc.escaped, result, idx+1)

	}
}

func TestTrimPrefixes(t *testing.T) {
	var testCases = []struct {
		s        string
		prefixes []string
		result   string
	}{
		{
			"http://index.docker.io",
			[]string{"http://", "https://"},
			"index.docker.io",
		},
		{
			"https://index.docker.io",
			[]string{"http://", "https://"},
			"index.docker.io",
		},
		{
			"index.docker.io",
			[]string{"http://", "https://"},
			"index.docker.io",
		},
		{
			"index.docker.io",
			[]string{"index.", "docker."},
			"io",
		},
		{
			"index.docker.io",
			[]string{"docker.", "index."},
			"docker.io",
		},
	}

	for idx, tc := range testCases {
		assert.Equal(t, tc.result, TrimPrefixes(tc.s, tc.prefixes...), idx+1)
	}
}

func TestEscapeNotificationOpts(t *testing.T) {
	type A struct {
		B string
		C string
	}

	var testCases = []struct {
		opts     *A
		expected *A
	}{
		{
			&A{
				B: `Billy "the Kid" O'Conner`,
				C: `artificial"image`,
			},
			&A{
				B: "Billy \\\"the Kid\\\" O'Conner",
				C: "artificial\\\"image",
			},
		},
	}

	for idx, tc := range testCases {
		JsonEscapeStruct(tc.opts)
		assert.Equal(t, *tc.expected, *tc.opts, idx+1)
	}
}
