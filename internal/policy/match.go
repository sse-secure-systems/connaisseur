package policy

import (
	"connaisseur/internal/utils"
	"strings"

	"github.com/sirupsen/logrus"
)

type Match struct {
	// corresponding rule
	Rule Rule
	// number of components in the pattern,
	// meaning parts between slashes
	// (e.g. "*/foo/bar" has 3 components)
	componentCount int
	// length of each component
	componentLengths []int
	// length of the longest common prefix
	// for each component
	prefixLengths []int
}

// Creates a new match for a given rule and image.
func NewMatch(rule Rule, image string) *Match {
	components := strings.Split(rule.Pattern, "/")
	cc := len(components)
	cl := make([]int, cc)
	for idx := range cl {
		cl[idx] = len(components[idx])
	}
	ic := strings.Split(image, "/")
	pl := make([]int, cc)
	for idx := range components {
		pl[idx] = len(utils.LongestCommonPrefix([]string{components[idx], ic[idx]}))
	}

	return &Match{Rule: rule, componentCount: cc, componentLengths: cl, prefixLengths: pl}
}

// Compare compares match m1 against another match m2 and returns
// the one with the most specific pattern. If both patterns are
// equally specific, the match that was called is returned.
//
// The most specific pattern is the one with the most components.
// If both patterns have the same number of components, the one
// with the left most component with the bigger length is returned.
// If both patterns have the same number of components and the
// same length of the left most component, the one with the left
// most component with the longest common prefix is returned.
func (m1 *Match) Compare(m2 *Match) *Match {
	if m1.componentCount > m2.componentCount {
		return m1
	} else if m1.componentCount < m2.componentCount {
		return m2
	} else {
		for idx := range m1.prefixLengths {
			if m1.prefixLengths[idx] > m2.prefixLengths[idx] {
				return m1
			} else if m1.prefixLengths[idx] < m2.prefixLengths[idx] {
				return m2
			}
		}
		for idx := range m1.componentLengths {
			if m1.componentLengths[idx] > m2.componentLengths[idx] {
				return m1
			} else if m1.componentLengths[idx] < m2.componentLengths[idx] {
				return m2
			}
		}
	}
	logrus.Warnf("identical rules: %s, %s", m1.Rule.Pattern, m2.Rule.Pattern)
	return m1
}
