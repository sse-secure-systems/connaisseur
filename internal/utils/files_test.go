package utils

import (
	"path/filepath"
	"testing"

	"github.com/stretchr/testify/assert"
)

// Links to the directory with test files such that tests work with absolute paths on different
// machines
func localTestDirectory() string {
	base, err := filepath.Abs(filepath.Dir("../../test/testdata/filesystem/"))
	if err != nil {
		panic("Can't get local dir")
	}
	return base
}

func TestSafeFileName(t *testing.T) {
	var testCases = []struct {
		base           string
		elements       []string
		resultRelative string
		err            string
	}{
		{ // Works in usual case, with prepended separators
			localTestDirectory() + "/home",
			[]string{"/test"},
			"/home/test",
			"",
		},
		{ // Works without separators
			localTestDirectory() + "/a",
			[]string{"b", "c"},
			"/a/b/c",
			"",
		},
		{ // Works with relative base path, too
			"../../test/testdata/filesystem/a",
			[]string{"b", "c"},
			"/a/b/c",
			"",
		},
		{ // Changing directory works within path element
			localTestDirectory() + "/a",
			[]string{"b/..", "non_existant/../b/c"},
			"/a/b/c",
			"",
		},
		{ // Simple escape is not possible
			localTestDirectory() + "/a",
			[]string{"..", "home"},
			"",
			"goes beyond its parent path element",
		},
		{ // Just base directory is fine
			localTestDirectory() + "/home",
			[]string{},
			"/home",
			"",
		},
		{ // Just base directory is fine with trailing /
			localTestDirectory() + "/home/",
			[]string{},
			"/home",
			"",
		},
		{ // Resulting directory should be clean
			localTestDirectory() + "/a",
			[]string{"/", "b", "///c/"},
			"/a/b/c",
			"",
		},
		{ // Escape via symlink to file prefixed with parent directory name is not possible
			localTestDirectory() + "/a",
			[]string{"x"},
			"",
			"goes beyond its parent directory",
		},
		{ // Non-existing files cannot be resolved
			localTestDirectory() + "/a",
			[]string{"b", "x"},
			"",
			"failed to resolve",
		},
		{ // Non-existing base direcories cannot be resolved
			localTestDirectory() + "/c/d",
			[]string{},
			"",
			"failed to resolve",
		},
		{ // Even intermediate escape is not possible
			localTestDirectory() + "/a",
			[]string{"..", "a", "b"},
			"",
			"goes beyond its parent path element",
		},
	}
	for _, tc := range testCases {
		resolved, err := SafeFileName(tc.base, tc.elements...)

		if tc.err != "" {
			assert.NotNil(t, err, resolved)
			assert.ErrorContains(t, err, tc.err)
		} else {
			assert.Nil(t, err)
			assert.Equal(t, localTestDirectory()+tc.resultRelative, resolved)
		}
	}
}
