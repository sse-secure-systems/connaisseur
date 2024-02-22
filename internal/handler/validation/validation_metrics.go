package validation

import (
	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promauto"
)

var (
	numImageValidations = promauto.NewCounterVec(prometheus.CounterOpts{
		Name: "connaisseur_validations_total",
		Help: "The total number of image validations performed by Connaisseur",
	}, []string{"type", "validator_name", "result"})

	numImageValidationsSuccessful = promauto.NewCounterVec(prometheus.CounterOpts{
		Name: "connaisseur_validations_successful_total",
		Help: "The total number of image validations that were successful",
	}, []string{"type", "validator_name"})

	numImageValidationsFailed = promauto.NewCounterVec(prometheus.CounterOpts{
		Name: "connaisseur_validations_failed_total",
		Help: "The total number of image validations that failed",
	}, []string{"type", "validator_name"})

	numImageValidationsSkipped = promauto.NewCounterVec(prometheus.CounterOpts{
		Name: "connaisseur_validations_skipped_total",
		Help: "The total number of image validations that were skipped",
	}, []string{"type", "validator_name", "reason"})

	numImageValidationsTimeouted = promauto.NewCounterVec(prometheus.CounterOpts{
		Name: "connaisseur_validations_timeouted_total",
		Help: "The total number of image validations that timed out",
	}, []string{"type", "validator_name"})
)

// Increments the number of total and successful validations.
func IncValidationsSuccessful(validatorType, validatiorName string) {
	numImageValidations.WithLabelValues(validatorType, validatiorName, "success").Inc()
	numImageValidationsSuccessful.WithLabelValues(validatorType, validatiorName).Inc()
}

// Increments the number of total and failed validations.
func IncValidationsFailed(validatorType, validatiorName string) {
	numImageValidations.WithLabelValues(validatorType, validatiorName, "error").Inc()
	numImageValidationsFailed.WithLabelValues(validatorType, validatiorName).Inc()
}

// Increments the number of skipped validations, but not that of total.
func IncValidationsSkipped(validatorType, validatiorName, reason string) {
	numImageValidationsSkipped.WithLabelValues(validatorType, validatiorName, reason).Inc()
}

// Increments the number of total and timed out validations.
func IncValidationsTimeouted(validatorType, validatiorName string) {
	numImageValidations.WithLabelValues(validatorType, validatiorName, "error").Inc()
	numImageValidationsTimeouted.WithLabelValues(validatorType, validatiorName).Inc()
}
