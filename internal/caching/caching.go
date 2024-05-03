package caching

import (
	"connaisseur/internal/constants"
	"context"
	"os"
	"strconv"
	"time"

	"github.com/sirupsen/logrus"
)

type Cacher interface {
	Close() error
	Del(ctx context.Context, keys ...string) error
	Get(ctx context.Context, key string) (string, error)
	Keys(ctx context.Context, pattern string) ([]string, error)
	Set(ctx context.Context, key string, value interface{}) error
	Ping(ctx context.Context) error
}

func NewCacher() Cacher {
	configuredExpirySeconds, ok := os.LookupEnv(constants.CacheExpirySeconds)

	var expirySeconds int64
	if !ok {
		expirySeconds = constants.DefaultCacheExpirySeconds
	} else {
		parsedExpirySeconds, err := strconv.ParseInt(configuredExpirySeconds, 10, 64)
		if err != nil {
			logrus.Warnf("Couldn't parse cache expiry configuration '%s', defaulting to %d", configuredExpirySeconds, constants.DefaultCacheExpirySeconds)
			expirySeconds = constants.DefaultCacheExpirySeconds
		} else {
			expirySeconds = parsedExpirySeconds
		}
	}
	// If expiry is set to 0 or less, use a "cache" that doesn't do anything
	if expirySeconds <= 0 {
		return EmptyCache{}
	}

	return NewRedis(time.Duration(expirySeconds) * time.Second)
}
