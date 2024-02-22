package handler

import (
	"connaisseur/internal/constants"
	"connaisseur/test/testhelper"
	"context"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/stretchr/testify/assert"
)

func TestHandleStart(t *testing.T) {
	handler := http.HandlerFunc(HandleStart)

	ctx := context.Background()
	redis := testhelper.NewFailingCache(t, []testhelper.KeyValuePair{}, []string{}, true)
	ctx = context.WithValue(ctx, constants.Cache, redis)

	req := testhelper.MockRequest("GET", ctx, nil)
	resp := httptest.NewRecorder()
	handler.ServeHTTP(resp, req)

	assert.Equal(t, http.StatusServiceUnavailable, resp.Code)

	ctx = context.Background()
	redis = testhelper.NewFailingCache(t, []testhelper.KeyValuePair{}, []string{}, false)
	ctx = context.WithValue(ctx, constants.Cache, redis)

	req = testhelper.MockRequest("GET", ctx, nil)
	resp = httptest.NewRecorder()
	handler.ServeHTTP(resp, req)

	assert.Equal(t, http.StatusOK, resp.Code)

	req = testhelper.MockRequest("POST", ctx, nil)
	resp = httptest.NewRecorder()
	handler.ServeHTTP(resp, req)

	assert.Equal(t, http.StatusMethodNotAllowed, resp.Code)
}
