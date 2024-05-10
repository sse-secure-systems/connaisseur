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
	t.Setenv(constants.CacheExpirySecondsKey, "0")
	c := NewCacher()
	assert.IsType(t, EmptyCache{}, c)
}

func TestNewCacherInvalidConfig(t *testing.T) {
	t.Setenv(constants.CacheExpirySecondsKey, "not a number")
	c := NewCacher()
	assert.IsType(t, Redis{}, c)
}

func TestCacheErrorsDefault(t *testing.T) {
	assert.True(t, CacheErrors())
}

func TestCacheErrorsTrue(t *testing.T) {
	t.Setenv(constants.CacheErrorsKey, "true")
	assert.True(t, CacheErrors())
}

func TestCacheErrorsFalse(t *testing.T) {
	t.Setenv(constants.CacheErrorsKey, "0")
	assert.False(t, CacheErrors())
}

func TestCacheErrorsInvalid(t *testing.T) {
	t.Setenv(constants.CacheErrorsKey, "not a bool")
	assert.True(t, CacheErrors())
}
