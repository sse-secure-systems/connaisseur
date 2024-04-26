package caching

import (
	"connaisseur/internal/constants"
	"context"
	"time"
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
	return NewRedis(constants.DefaultCacheExpirySeconds * time.Second)
}
