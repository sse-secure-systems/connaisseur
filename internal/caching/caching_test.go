package caching

import (
	"connaisseur/internal/constants"
	"context"
	"os"
	"os/exec"
	"testing"

	"github.com/alicebob/miniredis/v2"
	"github.com/redis/go-redis/v9"
	"github.com/stretchr/testify/assert"
)

const PRE = "../../test/testdata/"

func TestRedis(t *testing.T) {
	constants.RedisCertDir = PRE + "caching/00_cert"

	c := NewCacher()
	assert.IsType(t, Redis{}, c)
	re := c.(Redis)

	r := miniredis.RunT(t)
	rdb := redis.NewClient(&redis.Options{
		Addr: r.Addr(),
	})
	re.redisClient = rdb

	defer re.Close()

	ctx := context.Background()
	re.Set(ctx, "key", "value", 0)

	val, _ := re.Get(ctx, "key")
	assert.Equal(t, "value", val)

	vals, _ := re.Keys(ctx, "*")
	assert.Equal(t, []string{"key"}, vals)

	re.Del(ctx, "key")
	_, err := re.Get(ctx, "key")
	assert.Error(t, err)

	err = re.Ping(ctx)
	assert.NoError(t, err)

	re.Close()
	err = re.Ping(ctx)
	assert.Error(t, err)
}

func TestRedisErrors(t *testing.T) {
	// This test is a bit tricky. We want to test the error handling of the
	// redis client, but we can't do that in the same process, because the
	// command will do an os.Exit(1) on error. So we start a new process
	// with the TEST_CASE environment variable set to 1 or 2, which will
	// cause the redis client to fail. We then check if the process exited
	// with an error.
	switch os.Getenv("TEST_CASE") {
	case "1":
		constants.RedisCertDir = PRE + "caching/01_err"
		redisClient()
	case "2":
		constants.RedisCertDir = PRE + "not_found"
		redisClient()
	default:
		cmd := exec.Command(os.Args[0], "-test.run=TestRedisErrors")
		cmd.Env = append(os.Environ(), "TEST_CASE=1")
		err := cmd.Run()
		e, ok := err.(*exec.ExitError)
		assert.True(t, ok)
		assert.False(t, e.Success())

		cmd = exec.Command(os.Args[0], "-test.run=TestRedisErrors")
		cmd.Env = append(os.Environ(), "TEST_CASE=2")
		err = cmd.Run()
		e, ok = err.(*exec.ExitError)
		assert.True(t, ok)
		assert.False(t, e.Success())
	}
}
