package testhelper

import (
	"context"
	"fmt"
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"strings"
	"sync"

	"github.com/docker/go/canonical/json"
	"github.com/theupdateframework/notary/tuf/data"
)

type ctrl struct {
	Calls           int
	ReceivedBody    string
	ReceivedHeaders map[string][]string
	AllBodies       []string
	mutex           *sync.Mutex
}

func (c *ctrl) mockWebhookHandler(w http.ResponseWriter, r *http.Request) {
	// prevents data races
	c.mutex.Lock()
	c.Calls++

	c.ReceivedHeaders = r.Header
	if r.Body != nil {
		if data, err := io.ReadAll(r.Body); err == nil {
			c.ReceivedBody = string(data)
			c.AllBodies = append(c.AllBodies, c.ReceivedBody)
		}
	}

	if c.ReceivedBody != "allow_no_header" && c.ReceivedBody != "{\"allow_no_header\":true}" {
		if r.Header.Get("Content-Type") != "application/json" &&
			r.Header.Get("Content-Type") != "my/weird/format" {
			http.Error(w, "Content-Type header is not application/json", http.StatusBadRequest)
			return
		}
	}

	if c.ReceivedBody == "fail" || c.ReceivedBody == "{\"fail\":true}" {
		http.Error(w, "fail", http.StatusInternalServerError)
		return
	}
	c.mutex.Unlock()

	w.WriteHeader(http.StatusOK)
	_, err := w.Write([]byte("ok"))
	if err != nil {
		panic(
			fmt.Errorf(
				"an unexpected error occurred during writing back the response in the context of the mockWebhookHandler",
			),
		)
	}
}

func MockRequest(method string, ctx context.Context, body io.Reader) *http.Request {
	req := httptest.NewRequest(method, "https://example.com", body)
	req = req.WithContext(ctx)
	if body != nil {
		req.Header.Set("Content-Type", "application/json")
	}

	return req
}

func HTTPWebhookMock() (*httptest.Server, *ctrl) {
	c := &ctrl{Calls: 0, mutex: &sync.Mutex{}}

	handler := http.NewServeMux()
	handler.HandleFunc("/", c.mockWebhookHandler)

	return httptest.NewServer(handler), c
}

type NotaryMockCtrl struct {
	base string
	auth bool
}

func NotaryMock(base string, auth bool) *httptest.Server {
	ncrtl := &NotaryMockCtrl{base: base, auth: auth}

	handler := http.NewServeMux()
	handler.HandleFunc("/", ncrtl.handleDefault)
	handler.HandleFunc("/token", ncrtl.handleToken)
	handler.HandleFunc("/v2/docker.io/", ncrtl.handleGetTrustData)

	return httptest.NewServer(handler)
}

func (ncrtl *NotaryMockCtrl) handleDefault(w http.ResponseWriter, r *http.Request) {
	if ncrtl.auth == true {
		if !strings.HasPrefix(r.Header.Get("Authorization"), "Bearer ") {
			w.Header().
				Set("www-authenticate", fmt.Sprintf(`Bearer realm="http://%s/token",service="auth",scope="repository:catalog:*"`, r.Host))
			w.WriteHeader(http.StatusUnauthorized)
			return
		}
	}

	w.WriteHeader(http.StatusOK)
	_, err := w.Write([]byte("ok"))
	if err != nil {
		panic(
			fmt.Errorf(
				"an unexpected error occurred during writing back the the response in the context of default handling of NotaryMockCtrl",
			),
		)
	}
}

func (ncrtl *NotaryMockCtrl) handleToken(w http.ResponseWriter, r *http.Request) {
	scope := strings.Split(strings.Split(r.URL.Query().Get("scope"), ":")[1], "/")
	if scope[len(scope)-1] == "alice-image" {
		username, password, ok := r.BasicAuth()
		if !ok || username != "test" || password != "test" {
			w.WriteHeader(http.StatusUnauthorized)
			return
		}
	}

	w.WriteHeader(http.StatusOK)
	_, err := w.Write([]byte(`{"token": "a.b.c"}`))
	if err != nil {
		panic(
			fmt.Errorf(
				"an unexpected error occurred during writing back the response in the context of token handling of NotaryMockCtrl",
			),
		)
	}
}

func (ncrtl *NotaryMockCtrl) handleGetTrustData(w http.ResponseWriter, r *http.Request) {
	if r.Header.Get("Authorization") != "Bearer a.b.c" {
		w.WriteHeader(http.StatusUnauthorized)
		return
	}

	if r.URL.Path == "/v2/docker.io/library/sample-image/_trust/tuf/return-invalid-response-body-please.json" {
		w.Header().Set("Content-Length", "1")
		return
	}

	path := strings.TrimPrefix(r.URL.Path, "/v2/docker.io/library/")
	repo := strings.Split(path, "/")[0]
	file := strings.TrimPrefix(path, repo+"/_trust/tuf/")

	fileBytes, err := os.ReadFile(
		fmt.Sprintf("%s/%s/%s", ncrtl.base, repo, file),
	)

	if err != nil {
		w.WriteHeader(http.StatusNotFound)
		return
	}

	var signed data.Signed
	err = json.Unmarshal(fileBytes, &signed)
	if err != nil {
		// if the file is not a json or in an invalid format,
		// return the raw bytes
		w.WriteHeader(http.StatusOK)
		_, err = w.Write(fileBytes)
		if err != nil {
			panic(
				fmt.Errorf(
					"an unexpected error occurred during writing back the response in the context of a file that is either non-json or in an invalid format",
				),
			)
		}
		return
	}
	signedBytes, err := json.Marshal(signed)
	if err != nil {
		panic(fmt.Errorf("should've been able to marshal to data from %s", file))
	}

	w.WriteHeader(http.StatusOK)
	_, err = w.Write(signedBytes)
	if err != nil {
		panic(fmt.Errorf("an unexpected error occurred during writing back the response"))
	}
}
