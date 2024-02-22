package validation

import (
	"testing"

	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/testutil"
	"github.com/stretchr/testify/assert"
)

func TestMetrics(t *testing.T) {
	forloopTwoArgs(3, IncValidationsSuccessful, "notary", "test")
	forloopTwoArgs(4, IncValidationsSuccessful, "notary", "test2")
	forloopTwoArgs(5, IncValidationsFailed, "cosign", "default")
	forloopThreeArgs(2, IncValidationsSkipped, "notaryv2", "test", "automatic child approval")

	vec := numImageValidationsSuccessful.MustCurryWith(prometheus.Labels{"type": "notary"})
	m1 := vec.WithLabelValues("test")
	m2 := vec.WithLabelValues("test2")
	assert.Equal(t, float64(7), testutil.ToFloat64(m1)+testutil.ToFloat64(m2))
	assert.Equal(t, float64(3), testutil.ToFloat64(numImageValidationsSuccessful.WithLabelValues("notary", "test")))
	assert.Equal(
		t,
		float64(5),
		testutil.ToFloat64(numImageValidationsFailed.WithLabelValues("cosign", "default")),
	)
	assert.Equal(t, float64(2), testutil.ToFloat64(numImageValidationsSkipped.WithLabelValues("notaryv2", "test", "automatic child approval")))
}

func forloopTwoArgs(i int, f func(string, string), arg1, arg2 string) {
	for j := 0; j < i; j++ {
		f(arg1, arg2)
	}
}

func forloopThreeArgs(i int, f func(string, string, string), arg1, arg2, arg3 string) {
	for j := 0; j < i; j++ {
		f(arg1, arg2, arg3)
	}
}
