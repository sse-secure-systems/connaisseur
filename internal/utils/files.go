package utils

import (
	"fmt"
	"path/filepath"
	"strings"
)

// SafeFileName returns the absolute file or directory name in (a child of) the baseDir directory
// that is described by pathElements. baseDir is assumed to provided by the application, in
// particular it shouldn't include external content.
//
// Each path element is seen as authoritative, i.e. a folder described by its n'th element cannot be
// "left" by its (n+1)'th element.
// In particular, path injections like '../' are only possible within each provided path element.
func SafeFileName(baseDir string, pathElements ...string) (string, error) {
	path, err := filepath.Abs(baseDir)
	if err != nil {
		return "", fmt.Errorf("failed to resolve %s: %s", baseDir, err)
	}

	for _, elem := range pathElements {
		resolved := filepath.Clean(path + "/" + elem)
		if strings.HasPrefix(resolved, path) {
			path = resolved
		} else {
			return "", fmt.Errorf("path element '%s' goes beyond its parent path element %s", elem, path)
		}
	}

	// Check the remainder is not a symlink to somewhere else
	finalDir := filepath.Dir(
		path,
	) + "/" // Final '/' is needed, otherwise a/x pointing to ax could "escape" a/ with respect to the HasPrefix check below
	finalPath, err := filepath.EvalSymlinks(path)
	if err != nil {
		return "", fmt.Errorf("failed to resolve %s: %s", path, err)
	}

	if strings.HasPrefix(finalPath, finalDir) {
		return finalPath, nil
	} else {
		return "", fmt.Errorf("symlink on %s goes beyond its parent directory %s", path, finalDir)
	}
}
