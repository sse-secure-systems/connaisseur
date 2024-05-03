package caching

import (
	"connaisseur/internal/constants"
	"testing"

	"github.com/stretchr/testify/assert"
)

func TestMain(m *testing.M) {
	constants.RedisCertDir = PRE + "caching/00_cert"
}

func TestNewCacherDefault(t *testing.T) {
	c := NewCacher()
	assert.IsType(t, Redis{}, c)
}

func TestNewCacherCachingDisabled(t *testing.T) {
	t.Setenv(constants.CacheExpirySeconds, "0")
	c := NewCacher()
	assert.IsType(t, EmptyCache{}, c)
}

func TestNewCacherInvalidConfig(t *testing.T) {
	t.Setenv(constants.CacheExpirySeconds, "not a number")
	c := NewCacher()
	assert.IsType(t, Redis{}, c)
}
