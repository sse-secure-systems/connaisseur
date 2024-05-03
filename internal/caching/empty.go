package caching

import (
	"context"
	"fmt"
)

type EmptyCache struct{}

func (c EmptyCache) Close() error {
	return nil
}

func (c EmptyCache) Del(ctx context.Context, keys ...string) error {
	return nil
}

func (c EmptyCache) Get(ctx context.Context, key string) (string, error) {
	return "", fmt.Errorf("cache disabled")
}

func (c EmptyCache) Keys(ctx context.Context, pattern string) ([]string, error) {
	return nil, nil
}

func (c EmptyCache) Set(ctx context.Context, key string, value interface{}) error {
	return nil
}

func (c EmptyCache) Ping(ctx context.Context) error {
	return nil
}
