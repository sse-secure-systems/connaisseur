package handler

import (
	"testing"

	"github.com/prometheus/client_golang/prometheus/testutil"
	"github.com/stretchr/testify/assert"
)

func TestMetrics(t *testing.T) {
	forloop(2, IncAdmissionsReceived)
	forloop(3, IncAdmissionsAdmitted)

	assert.Equal(t, float64(2), testutil.ToFloat64(numAdmissionsReceived))
	assert.Equal(t, float64(3), testutil.ToFloat64(numAdmissionsAdmitted))
}

func forloop(i int, f func()) {
	for j := 0; j < i; j++ {
		f()
	}
}
