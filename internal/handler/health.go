package handler

import (
	"connaisseur/internal/constants"
	"net/http"
)

// HandleHealth handles health checks. It returns a 200 OK.
func HandleHealth(w http.ResponseWriter, r *http.Request) {
	switch r.Method {
	case http.MethodGet:
		w.WriteHeader(http.StatusOK)
	default:
		http.Error(w, constants.MethodNotAllowed, http.StatusMethodNotAllowed)
	}
}
