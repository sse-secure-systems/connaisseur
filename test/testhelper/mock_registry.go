package testhelper

import (
	"connaisseur/internal/utils"
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
	"strings"
)

type RegistryCtrl struct {
	base string
}

func MockRegistry(base string) *httptest.Server {
	rctrl := &RegistryCtrl{base: base}

	handler := http.NewServeMux()
	handler.HandleFunc("/v2/", rctrl.HandleV2)
	return httptest.NewServer(handler)
}

func (rctrl RegistryCtrl) HandleV2(w http.ResponseWriter, r *http.Request) {
	path := r.URL.Path[len("/v2/"):]

	if path == "" {
		ok(w)
	} else {
		rctrl.HandlePath(w, path)
	}
}

func ok(w http.ResponseWriter) {
	w.WriteHeader(http.StatusOK)
	_, err := w.Write([]byte("ok"))
	if err != nil {
		panic(
			fmt.Errorf(
				"an unexpected error occurred during writing back the response in the context of the mockRegistryHandler",
			),
		)
	}
}

func (rctrl RegistryCtrl) HandlePath(w http.ResponseWriter, path string) {
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

	w.WriteHeader(http.StatusOK)
	_, err = w.Write(file)
	if err != nil {
		panic(err)
	}
}
