package utils

import (
	"testing"

	"github.com/stretchr/testify/assert"
	core "k8s.io/api/core/v1"
)

func TestSetSubstract(t *testing.T) {
	var testCases = []struct {
		list1     []string
		list2     []string
		substract []string
	}{
		{
			[]string{"a", "b", "c"},
			[]string{"a", "b", "c"},
			[]string{},
		},
		{
			[]string{"d", "e", "f"},
			[]string{"a", "b", "c"},
			[]string{"d", "e", "f"},
		},
		{
			[]string{"a", "b", "c", "d", "e", "f"},
			[]string{"a", "b", "c"},
			[]string{"d", "e", "f"},
		},
		{
			[]string{"a", "b", "c"},
			[]string{"a", "b", "c", "d", "e", "f"},
			[]string{},
		},
		{
			[]string{"a", "a", "b", "b"},
			[]string{"a"},
			[]string{"b"},
		},
	}

	for _, tc := range testCases {
		sub := SetSubstract(tc.list1, tc.list2)
		assert.Equal(t, len(tc.substract), len(sub))
		for _, v := range tc.substract {
			assert.Contains(t, sub, v)
		}
	}
}

func TestUniq(t *testing.T) {
	var testCases = []struct {
		list1 []string
		uniq  []string
	}{
		{
			[]string{"a", "b", "c"},
			[]string{"a", "b", "c"},
		},
		{
			[]string{"a", "b", "c", "a", "b", "c"},
			[]string{"a", "b", "c"},
		},
		{
			[]string{"a", "a", "a", "a", "a", "b"},
			[]string{"a", "b"},
		},
	}

	for _, tc := range testCases {
		uniq := uniq(tc.list1)
		assert.Equal(t, len(tc.uniq), len(uniq))
		for _, v := range tc.uniq {
			assert.Contains(t, uniq, v)
		}
	}
}

func TestMap(t *testing.T) {
	containers := []core.Container{
		{Image: "a"}, {Image: "b"}, {Image: "c"},
	}
	containerStrings := Map(containers, func(c core.Container) string {
		return c.Image
	})
	assert.Equal(t, len(containers), len(containerStrings))
	for idx, c := range containers {
		assert.Equal(t, containerStrings[idx], c.Image)
	}

	someStrings := []string{"a", "bb", "cccc", "ddd", "e"}
	someLengths := Map(someStrings, func(s string) int {
		return len(s)
	})
	assert.Equal(t, len(someStrings), len(someLengths))
	for idx, s := range someStrings {
		assert.Equal(t, someLengths[idx], len(s))
	}
}
