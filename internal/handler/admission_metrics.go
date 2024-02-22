package handler

import (
	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promauto"
)

var (
	numAdmissionsReceived = promauto.NewCounter(prometheus.CounterOpts{
		Name: "connaisseur_requests_total",
		Help: "The total number of admission requests posed to Connaisseur",
	})

	numAdmissionsAdmitted = promauto.NewCounter(prometheus.CounterOpts{
		Name: "connaisseur_requests_admitted_total",
		Help: "The total number of admission requests that were admitted",
	})

	numAdmissionsDenied = promauto.NewCounterVec(prometheus.CounterOpts{
		Name: "connaisseur_requests_denied_total",
		Help: "The total number of admission requests that were denied",
	}, []string{"timeout"})
)

// Increments the number of admission requests received.
func IncAdmissionsReceived() {
	numAdmissionsReceived.Inc()
}

// Increments the number of admitted admission requests.
func IncAdmissionsAdmitted() {
	numAdmissionsAdmitted.Inc()
}

// Increments the number of denied admission requests.
func IncAdmissionsDenied(timeout bool) {
	if timeout {
		numAdmissionsDenied.WithLabelValues("true").Inc()
	} else {
		numAdmissionsDenied.WithLabelValues("false").Inc()
	}
}
