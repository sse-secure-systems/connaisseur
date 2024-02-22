package handler

import (
	"connaisseur/internal/caching"
	"connaisseur/internal/constants"
	"net/http"
)

// HandleStart tries to ping the redis. Return 200 if successful, 503 otherwise.
func HandleStart(w http.ResponseWriter, r *http.Request) {
	switch r.Method {
	case http.MethodGet:
		ctx := r.Context()
		cache := ctx.Value(constants.Cache).(caching.Cacher)

		if err := cache.Ping(ctx); err != nil {
			http.Error(w, constants.ServiceUnavailable, http.StatusServiceUnavailable)
			return
		}

		w.WriteHeader(http.StatusOK)
	default:
		http.Error(w, constants.MethodNotAllowed, http.StatusMethodNotAllowed)
	}
}
