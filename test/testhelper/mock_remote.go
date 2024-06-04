package testhelper

import (
	"fmt"
	"net/http"
	"net/http/httptest"
)

type RemoteCtrl struct {
	Username string
	Password string
}

func MockRemote() (*httptest.Server, *RemoteCtrl) {
	rctrl := &RemoteCtrl{}

	handler := http.NewServeMux()
	handler.HandleFunc("/", rctrl.HandleRemote)
	return httptest.NewServer(handler), rctrl
}

func (rctrl *RemoteCtrl) HandleRemote(w http.ResponseWriter, r *http.Request) {
	u, p, ok_ := r.BasicAuth()
	if ok_ {
		rctrl.Username = u
		rctrl.Password = p
	} else {
		rctrl.Username = ""
		rctrl.Password = ""
	}

	w.Header().
		Set("www-authenticate", fmt.Sprintf(`Bearer realm="http://%s/token"`, r.Host))
	w.WriteHeader(http.StatusUnauthorized)
}
