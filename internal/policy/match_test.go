package policy

import (
	"testing"

	"github.com/stretchr/testify/assert"
)

const imageTag string = "docker.io/securesystemsengineering/sample:v1"

const imageDigest string = "docker.io/securesystemsengineering/sample@sha256:1388abc7a12532836c3a81bdb0087409b15208f5aeba7a87aedcfd56d637c145"

func TestNewMatch(t *testing.T) {
	var testCases = []struct {
		rule      Rule
		image     string
		compCount int
		compLen   []int
		preLen    []int
	}{
		{Rule{Pattern: ""}, "", 1, []int{0}, []int{0}},
		{Rule{Pattern: "*:*"}, imageTag, 1, []int{3}, []int{0}},
		{Rule{Pattern: "doc*/*"}, imageTag, 2, []int{4, 1}, []int{3, 0}},
		{Rule{Pattern: "*/sec*/*:*"}, imageTag, 3, []int{1, 4, 3}, []int{0, 3, 0}},
		{Rule{Pattern: "*@sha256:*"}, imageDigest, 1, []int{10}, []int{0}},
	}

	for idx, tc := range testCases {
		m := NewMatch(tc.rule, tc.image)

		assert.Equalf(t, tc.compCount, m.componentCount, "component count test case %d", idx+1)
		assert.Equalf(t, tc.compLen, m.componentLengths, "component length test case %d", idx+1)
		assert.Equalf(t, tc.preLen, m.prefixLengths, "prefix lengths test case %d", idx+1)
	}
}

func TestCompare(t *testing.T) {
	var testCases = []struct {
		r1       Rule
		r2       Rule
		image    string
		expected int
	}{
		// 1: Empty pattern works
		{Rule{Pattern: ""}, Rule{Pattern: "*"}, imageTag, 1},
		// 2: More components win
		{Rule{Pattern: "*:*"}, Rule{Pattern: "*/*"}, imageTag, 1},
		// 3: More components win
		{Rule{Pattern: "docker*/*"}, Rule{Pattern: "*/*/*"}, imageTag, 1},
		// 4: Longer component wins
		{Rule{Pattern: "*"}, Rule{Pattern: "*:*"}, imageTag, 1},
		// 5: Longer component wins
		{Rule{Pattern: "*/*"}, Rule{Pattern: "docker*/*"}, imageTag, 1},
		// 6: Left-most longer component wins
		{Rule{Pattern: "*/*/image:v1"}, Rule{Pattern: "*/sam*/*"}, imageTag, 1},
		// 7: Specificity counts, when same length
		{Rule{Pattern: "docker.i*/s*"}, Rule{Pattern: "docker.io/*"}, imageTag, 1},
		// 8: Tag is no component
		{Rule{Pattern: "*:test"}, Rule{Pattern: "*/*"}, imageTag, 1},
		// 9: Even though it's not its own component, length in tag still counts
		{
			Rule{Pattern: "securesystemsengineering/sample:*"},
			Rule{Pattern: "securesystemsengineering/sample:v*"},
			imageTag,
			1,
		},
		// 10: Equal patterns
		{Rule{Pattern: "*"}, Rule{Pattern: "*"}, imageTag, 0},
		// 11: Compare can return something other than the compared second match
		{Rule{Pattern: "*"}, Rule{Pattern: ""}, imageTag, -1},
	}

	for idx, tc := range testCases {
		m1 := NewMatch(tc.r1, tc.image)
		m2 := NewMatch(tc.r2, tc.image)

		if tc.expected <= 0 {
			assert.Equalf(t, m1, m1.Compare(m2), "test case %d", idx+1)
			assert.Equalf(t, m1, m2.Compare(m1), "test case %d", idx+1)
		}
		if tc.expected >= 0 {
			assert.Equalf(t, m2, m1.Compare(m2), "test case %d", idx+1)
			assert.Equalf(t, m2, m2.Compare(m1), "test case %d", idx+1)
		}
	}
}
