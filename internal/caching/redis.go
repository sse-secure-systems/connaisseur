package caching

import (
	"connaisseur/internal/constants"
	"context"
	"crypto/tls"
	"crypto/x509"
	"fmt"
	"os"
	"time"

	"github.com/redis/go-redis/v9"
	"github.com/sirupsen/logrus"
)

type Redis struct {
	redisClient *redis.Client
	expiry      time.Duration
}

func (r Redis) Close() error {
	return r.redisClient.Close()
}

func (r Redis) Del(ctx context.Context, keys ...string) error {
	return r.redisClient.Del(ctx, keys...).Err()
}

func (r Redis) Get(ctx context.Context, key string) (string, error) {
	return r.redisClient.Get(ctx, key).Result()
}

func (r Redis) Keys(ctx context.Context, pattern string) ([]string, error) {
	return r.redisClient.Keys(ctx, pattern).Result()
}

func (r Redis) Set(
	ctx context.Context,
	key string,
	value interface{},
) error {
	return r.redisClient.Set(ctx, key, value, r.expiry).Err()
}

func (r Redis) Ping(ctx context.Context) error {
	_, err := r.redisClient.Ping(ctx).Result()
	if err != nil {
		logrus.Errorf("redis ping failed: %s", err)
		return err
	}
	return nil
}

func NewRedis(expiry time.Duration) Redis {
	rdb := redisClient()
	return Redis{redisClient: rdb, expiry: expiry}
}

func redisClient() *redis.Client {
	host := os.Getenv("REDIS_HOST")
	pass := os.Getenv("REDIS_PASSWORD")

	cert, err := os.ReadFile(fmt.Sprintf("%s/tls.crt", constants.RedisCertDir))
	if err != nil {
		logrus.Fatalf("could not read redis cert: %s", err)
	}
	certPool := x509.NewCertPool()
	if !certPool.AppendCertsFromPEM(cert) {
		logrus.Fatal("failed to append redis certificate")
	}

	rdb := redis.NewClient(&redis.Options{
		Addr:     fmt.Sprintf("%s:%d", host, constants.DefaultRedisPort),
		Password: pass,
		TLSConfig: &tls.Config{
			RootCAs:    certPool,
			MinVersion: tls.VersionTLS12,
		},
	})
	return rdb
}
