package handler

import (
	"connaisseur/test/testhelper"
	"context"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/stretchr/testify/assert"
)

func TestHandleHealth(t *testing.T) {
	handler := http.HandlerFunc(HandleHealth)
	req := testhelper.MockRequest("GET", context.Background(), nil)
	resp := httptest.NewRecorder()
	handler.ServeHTTP(resp, req)
	assert.Equal(t, http.StatusOK, resp.Code)

	req = testhelper.MockRequest("POST", context.Background(), nil)
	resp = httptest.NewRecorder()
	handler.ServeHTTP(resp, req)
	assert.Equal(t, http.StatusMethodNotAllowed, resp.Code)

	req = testhelper.MockRequest("PUT", context.Background(), nil)
	resp = httptest.NewRecorder()
	handler.ServeHTTP(resp, req)
	assert.Equal(t, http.StatusMethodNotAllowed, resp.Code)
}
