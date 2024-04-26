package testhelper

import (
	"connaisseur/internal/caching"
	"connaisseur/internal/constants"
	"context"
	"fmt"
	"testing"
	"time"

	"github.com/alicebob/miniredis/v2"
	"github.com/redis/go-redis/v9"
)

type KeyValuePair struct {
	Key   string
	Value string
}

// FailingCache will work as expected except when Getting one of failingKeys
type FailingCache struct {
	db          *miniredis.Miniredis
	client      *redis.Client
	failingKeys []string
	pingFail    bool
}

func (c FailingCache) Close() error {
	c.db.Close()
	return c.client.Close()

}

func (c FailingCache) Del(ctx context.Context, keys ...string) error {
	return c.client.Del(ctx, keys...).Err()
}

func (c FailingCache) Get(ctx context.Context, key string) (string, error) {
	for _, k := range c.failingKeys {
		if k == key {
			return "", fmt.Errorf("cache consciously fails for key %s", key)
		}
	}
	return c.client.Get(ctx, key).Result()
}

func (c FailingCache) Keys(ctx context.Context, pattern string) ([]string, error) {
	return c.client.Keys(ctx, pattern).Result()
}

func (c FailingCache) Set(
	ctx context.Context,
	key string,
	value interface{},
) error {
	return c.client.Set(ctx, key, value, constants.DefaultCacheExpirySeconds*time.Second).Err()
}

func (c FailingCache) Ping(ctx context.Context) error {
	if c.pingFail {
		return fmt.Errorf("ping fail")
	}
	_, err := c.client.Ping(ctx).Result()
	return err
}

func NewFailingCache(t *testing.T, keys []KeyValuePair, failingKeys []string, pingFail bool) caching.Cacher {
	r := miniredis.RunT(t)

	for _, entry := range keys {
		err := r.Set(entry.Key, entry.Value)
		if err != nil {
			panic(
				fmt.Errorf(
					"an unexpected error occurred during setting a value for key %s",
					entry.Key,
				),
			)
		}
	}

	rdb := redis.NewClient(&redis.Options{
		Addr: r.Addr(),
	})

	return FailingCache{db: r, client: rdb, failingKeys: failingKeys, pingFail: pingFail}
}

func MockCache(t *testing.T, keys []KeyValuePair) caching.Cacher {
	return NewFailingCache(t, keys, []string{}, false)
}
