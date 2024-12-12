package testhelper

import (
	"connaisseur/internal/utils"
	"crypto/sha256"
	"crypto/tls"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
	"strings"
)

type NotationRegistryCtrl struct {
	base string
}

func NotationMockRegistry(base string) *httptest.Server {
	rctrl := &NotationRegistryCtrl{base: base}

	handler := http.NewServeMux()
	handler.HandleFunc("/v2/", rctrl.HandleV2)

	// Load the TLS certificate and key
	cert, err := tls.LoadX509KeyPair(fmt.Sprintf("%s/server-cert.pem", base), fmt.Sprintf("%s/server-key.pem", base))
	if err != nil {
		panic(fmt.Sprintf("failed to load TLS certificate and key: %v", err))
	}

	// Create a TLS configuration with the certificate and key
	tlsConfig := &tls.Config{
		Certificates: []tls.Certificate{cert},
	}

	server := httptest.NewUnstartedServer(handler)
	server.TLS = tlsConfig
	server.StartTLS()

	return server
}

func (rctrl NotationRegistryCtrl) HandleV2(w http.ResponseWriter, r *http.Request) {
	path := r.URL.Path[len("/v2/"):]

	if path == "" {
		ok(w)
	} else {
		rctrl.HandlePath(w, path)
	}
}

func (rctrl NotationRegistryCtrl) HandlePath(w http.ResponseWriter, path string) {
	fileName, err := utils.SafeFileName(rctrl.base, strings.Split(fmt.Sprintf("%s.json", path), "/")...)
	if err != nil {
		w.WriteHeader(http.StatusNotFound)
		return
	}
	file, err := os.ReadFile(fileName)
	if err != nil {
		w.WriteHeader(http.StatusNotFound)
		return
	}

	type_ := strings.Split(path, "/")[2]
	switch type_ {
	case "manifests":
		type temp struct {
			MediaType string `json:"mediaType"`
		}

		var t temp
		json.Unmarshal(file, &t)

		w.Header().Add("Content-Type", t.MediaType)
	case "blobs":
		w.Header().Add("Content-Type", "application/vnd.cncf.notary.payload.v1+json")
	}

	hash := sha256.Sum256(file)
	hashString := hex.EncodeToString(hash[:])

	w.Header().Add("Docker-Content-Digest", fmt.Sprintf("sha256:%s", hashString))
	w.WriteHeader(http.StatusOK)
	_, err = w.Write(file)
	if err != nil {
		panic(err)
	}
}
