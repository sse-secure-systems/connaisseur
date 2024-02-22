package utils

import (
	"testing"

	"github.com/stretchr/testify/assert"
)

func TestMax(t *testing.T) {
	var testCases = []struct {
		x   int
		y   int
		max int
	}{
		{
			x:   1,
			y:   2,
			max: 2,
		},
		{
			x:   2,
			y:   1,
			max: 2,
		},
	}

	for _, tc := range testCases {
		result := Max(tc.x, tc.y)
		assert.Equal(t, tc.max, result)
	}
}
