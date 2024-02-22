package alerting

import (
	"connaisseur/internal/constants"
	"connaisseur/test/testhelper"
	"context"
	"fmt"
	"testing"

	"github.com/stretchr/testify/assert"
)

func TestEvalAndSendNotification(t *testing.T) {
	var testCases = []struct {
		alertingFile string
		opts         *NotificationValues
		expectedBody string
		err          string
	}{
		{ // 1: valid admit
			"alerting/03_send_notif_test.yaml",
			&NotificationValues{Result: constants.NotificationResultSuccess},
			`{"cluster":"test","message":"CONNAISSEUR admitted a request"}`,
			"",
		},
		{ // 2: valid reject
			"alerting/03_send_notif_test.yaml",
			&NotificationValues{Result: constants.NotificationResultError, Error: fmt.Errorf("error")},
			`{"cluster":"test","message":"CONNAISSEUR rejected a request: error"}`,
			"",
		},
		{ // 3: valid admit with unspecified clusterId
			"alerting/04_send_notif_no_cluster.yaml",
			&NotificationValues{Result: constants.NotificationResultSuccess},
			`{"cluster":"not specified","message":"CONNAISSEUR admitted a request"}`,
			"",
		},
		{ // 4: error case
			"alerting/05_send_notif_tmpl_not_found.yaml",
			&NotificationValues{Result: constants.NotificationResultSuccess},
			``,
			"unable to get template file",
		},
	}

	for idx, tc := range testCases {
		al, err := LoadConfig(PRE, tc.alertingFile)
		assert.NoError(t, err, idx+1)

		srv, c := testhelper.HTTPWebhookMock()
		defer srv.Close()

		for i := range al.AdmitRequests.Receivers {
			r := al.AdmitRequests.Receivers[i].(*Channel)
			r.URL = srv.URL + "/"
		}
		for i := range al.RejectRequests.Receivers {
			r := al.RejectRequests.Receivers[i].(*Channel)
			r.URL = srv.URL + "/"
		}

		err = al.EvalAndSendNotifications(context.TODO(), tc.opts)
		if tc.err != "" {
			assert.Error(t, err, idx+1)
			assert.ErrorContains(t, err, tc.err, idx+1)
		} else {
			assert.NoError(t, err, idx+1)
			assert.Equal(t, tc.expectedBody, c.ReceivedBody, idx+1)
			assert.Equal(t, 1, c.Calls, idx+1)
		}
	}
}

func TestEvalAndSendNotificationExpire(t *testing.T) {
	al, err := LoadConfig(PRE, "alerting/03_send_notif_test.yaml")
	assert.NoError(t, err)

	srv, _ := testhelper.HTTPWebhookMock()
	defer srv.Close()

	for i := range al.AdmitRequests.Receivers {
		r := al.AdmitRequests.Receivers[i].(*Channel)
		r.URL = srv.URL + "/"
	}
	for i := range al.RejectRequests.Receivers {
		r := al.RejectRequests.Receivers[i].(*Channel)
		r.URL = srv.URL + "/"
	}

	ctx := context.Background()
	ctx, cancel := context.WithCancel(ctx)
	cancel()

	err = al.EvalAndSendNotifications(ctx, &NotificationValues{Result: constants.NotificationResultSuccess})
	assert.Error(t, err)
	assert.ErrorContains(t, err, "timeout")
}

func TestMultipleEvalAndSendNotifications(t *testing.T) {
	al, err := LoadConfig(PRE, "alerting/08_send_notif_multiple_ch.yaml")
	assert.NoError(t, err)

	srv, c := testhelper.HTTPWebhookMock()
	defer srv.Close()

	for i := range al.AdmitRequests.Receivers {
		r := al.AdmitRequests.Receivers[i].(*Channel)
		r.URL = srv.URL + "/"
	}
	for i := range al.RejectRequests.Receivers {
		r := al.RejectRequests.Receivers[i].(*Channel)
		r.URL = srv.URL + "/"
	}

	_ = al.EvalAndSendNotifications(context.TODO(), &NotificationValues{Result: constants.NotificationResultSuccess})

	assert.Equal(t, 2, c.Calls)
	for _, s := range []string{`{"prio":"69"}`, `{"prio":"1337"}`} {
		assert.Contains(t, c.AllBodies, s)
	}
}
