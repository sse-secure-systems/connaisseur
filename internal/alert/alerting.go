package alerting

import (
	"connaisseur/internal/constants"
	"context"
	"fmt"
)

type NotificationValues struct {
	// validation result, e.g. success, skipped, error, timeout, invalid
	Result string
	// error that occurred during validation
	Error error
	// comma separated list of images
	Images string
	// request id
	RequestId string
	// priority of the alert
	Priority int
	// pod id that is handling the request
	ConnaisseurPodId string
	// cluster id
	Cluster string
	// namespace of the request
	Namespace string
	// timestamp when the notification was processed
	Timestamp string
	// alert message
	AlertMessage string
}

func (a *Config) EvalAndSendNotifications(ctx context.Context, opts *NotificationValues) error {
	// update notification values with cluster id
	if a.ClusterId == "" {
		a.ClusterId = "not specified"
	}
	opts.Cluster = a.ClusterId

	var (
		receivers []Sender
		stream    string
	)

	// select the appropriate receivers and stream
	// based on the result of the admission request
	switch opts.Result {
	case constants.NotificationResultSuccess, constants.NotificationResultSkip:
		receivers = a.AdmitRequests.Receivers
		stream = "admit"
		opts.AlertMessage = "CONNAISSEUR admitted a request"
	case constants.NotificationResultError:
		receivers = a.RejectRequests.Receivers
		stream = "reject"
		opts.AlertMessage = fmt.Sprintf("CONNAISSEUR rejected a request: %s", opts.Error.Error())
	case constants.NotificationResultTimeout:
		receivers = a.RejectRequests.Receivers
		stream = "reject"
		opts.AlertMessage = fmt.Sprintf("CONNAISSEUR validation timed out for admission request %s", opts.RequestId)
	case constants.NotificationResultInvalid:
		receivers = a.RejectRequests.Receivers
		stream = "reject"
		opts.AlertMessage = fmt.Sprintf("CONNAISSEUR failed to parse admission request %s", opts.RequestId)
	default:
		return fmt.Errorf("unknown result type for alerting: %s", opts.Result)
	}

	errorChannel := make(chan error, len(receivers))

	for _, sender := range receivers {
		// Since we want blocking behavior if failOnError is set
		// but not otherwise, we need to distinguish these cases here
		var alertContext context.Context
		if sender.FailOnError() {
			alertContext = ctx
		} else {
			alertContext = context.Background()
		}
		go sender.Send(alertContext, *opts, errorChannel)
	}

	// Wait for all alerts that should block
	for i, rec := range receivers {
		select {
		case <-ctx.Done():
			return fmt.Errorf(
				"timeout after handling %d/%d receivers of %s alerts",
				i,
				len(receivers),
				stream,
			)
		case err := <-errorChannel:
			if err != nil {
				return fmt.Errorf(
					"failed sending a notification for receiver %s with FailOnError set: %s",
					rec.Name(),
					err,
				)
			}
		}
	}
	// Since Channel.Send also logs errors before returning, we get error logs and don't need
	// separate handling for those
	return nil
}
