package alerting

import (
	"connaisseur/internal/constants"
	"connaisseur/test/testhelper"
	"context"
	"os"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
)

func TestMain(m *testing.M) {
	constants.AlertTemplateDir = "../../test/testdata/alerts"
	os.Exit(m.Run())
}

func TestGenerateNotificationMessage(t *testing.T) {
	var testCases = []struct {
		template      string
		opts          *NotificationValues
		payloadFields map[string]interface{}
		expected      string
		expectedErr   string
	}{
		{ // 1: simple working case
			"06_template",
			&NotificationValues{
				ConnaisseurPodId: "1",
			},
			map[string]interface{}{},
			`{"name":"connaisseur_pod_id","value":"1"}`,
			"",
		},
		{ // 2: working case
			"07_opsgenie",
			&NotificationValues{
				AlertMessage:     "test1",
				Images:           "test2",
				ConnaisseurPodId: "test3",
				Timestamp:        time.Date(1970, time.January, 1, 0, 0, 0, 0, &time.Location{}).Format(time.RFC3339),
				Cluster:          "test4",
				Namespace:        "test5",
				RequestId:        "test6",
				Priority:         7,
			},
			map[string]interface{}{
				"responders": []string{"test8"},
				"visibleTo":  []string{"test9"},
				"tags":       []string{"test10"},
			},
			`{"actions":[],"alias":"test1 while deploying the images test2.","description":"test1 while deploying the following images:\n test2 \n\n Please check the logs of the ` + "`test3`" + ` for more details.","details":{"alert_created":"1970-01-01T00:00:00Z","cluster":"test4","namespace":"test5","pod":"test3","request_id":"test6"},"entity":"Connaisseur","message":"test1","priority":"P7","responders":["test8"],"tags":["test10"],"visibleTo":["test9"]}`,
			"",
		},
		{ // 3: template not found
			"404_notfound",
			&NotificationValues{},
			map[string]interface{}{},
			"",
			"unable to get template file",
		},
		{ // 4: render error
			"08_render_err",
			&NotificationValues{},
			map[string]interface{}{},
			"",
			"failed to render template",
		},
		{ // 5: invalida payload fields
			"06_template",
			&NotificationValues{},
			map[string]interface{}{
				"test": make(chan int),
			},
			``,
			"failed to marshal rendered template",
		},
		{ // 6: empty template creates no error
			"09_empty",
			&NotificationValues{},
			map[string]interface{}{},
			"",
			"",
		},
		{ // 7: triple brackets
			"14_triple_bracket",
			&NotificationValues{},
			map[string]interface{}{},
			``,
			"unexpected \"{\" in command",
		},
		{ // 8
			"15_mismatch_bracket",
			&NotificationValues{},
			map[string]interface{}{},
			"",
			"unexpected \"{\" in command",
		},
		{ // 9
			"16_single_bracket",
			&NotificationValues{},
			map[string]interface{}{},
			`{"prio":"{ priority }"}`,
			"",
		},
	}

	for idx, tc := range testCases {
		ch := &Channel{
			TemplateFile:  tc.template,
			ChannelName:   "test",
			PayloadFields: tc.payloadFields,
		}
		actual, err := ch.generateNotificationMessage(*tc.opts)

		if tc.expectedErr != "" {
			assert.ErrorContains(t, err, tc.expectedErr, idx+1)
		} else {
			assert.NoError(t, err, idx+1)
			assert.Equal(t, tc.expected, actual.String(), idx+1)
		}
	}
}

func TestSend(t *testing.T) {
	var testCases = []struct {
		template        string
		headers         []string
		opts            *NotificationValues
		expectedMsg     string
		expectedHeaders map[string][]string
		calls           int
	}{
		{ // 1: A "skip" notification works and defaults to application/json as Content-Type
			"06_template",
			[]string{},
			&NotificationValues{},
			`{"name":"connaisseur_pod_id","value":""}`,
			map[string][]string{"Content-Type": {"application/json"}},
			1,
		},
		{ // 2: Headers are passed along
			"06_template",
			[]string{"X-Test: test"},
			&NotificationValues{},
			`{"name":"connaisseur_pod_id","value":""}`,
			map[string][]string{"X-Test": {"test"}},
			1,
		},
		{ // 3: Multiple headers can be set and overwrite default application/json CT header
			"06_template",
			[]string{"X-Test: test:ing", "Content-Type: my/weird/format"},
			&NotificationValues{},
			`{"name":"connaisseur_pod_id","value":""}`,
			map[string][]string{"X-Test": {"test:ing"}, "Content-Type": {"my/weird/format"}},
			1,
		},
		{ // 4: Empty notifications are not sent
			"09_empty",
			[]string{},
			&NotificationValues{},
			"",
			map[string][]string{},
			0,
		},
		{ // 5: Weird capitalization doesn't interfere with setting headers
			"06_template",
			[]string{"CoNTeNt-TYpE: my/weird/format"},
			&NotificationValues{},
			`{"name":"connaisseur_pod_id","value":""}`,
			map[string][]string{"Content-Type": {"my/weird/format"}},
			1,
		},
		{ // 6: Empty content type produces empty header
			"10_allow_no_header",
			[]string{"COnTeNt-TYpE: "},
			&NotificationValues{},
			`{"allow_no_header":true}`,
			map[string][]string{"Content-Type": {""}},
			1,
		},
		{ // 7: Injection is not possible
			"06_template",
			[]string{},
			&NotificationValues{
				ConnaisseurPodId: "<script>alert(\"ISAINJECTION\")</script>",
			},
			`{"name":"connaisseur_pod_id","value":"\u003cscript\u003ealert(\"ISAINJECTION\")\u003c/script\u003e"}`,
			map[string][]string{},
			1,
		},
	}

	for idx, tc := range testCases {
		srv, c := testhelper.HTTPWebhookMock()
		defer srv.Close()
		ch := &Channel{
			ChannelName:  "test",
			TemplateFile: tc.template,
			URL:          srv.URL + "/",
			Headers:      tc.headers,
			Fail:         true,
		}
		errorChannel := make(chan error)
		defer close(errorChannel)
		go ch.Send(context.TODO(), *tc.opts, errorChannel)

		assert.Nil(t, <-errorChannel, "test case %d", idx+1)
		srv.Close()
		assert.Equal(t, tc.calls, c.Calls, "test case %d", idx+1)
		assert.Equal(t, tc.expectedMsg, c.ReceivedBody, "test case %d", idx+1)
		for k, v := range tc.expectedHeaders {
			assert.Equal(t, v, c.ReceivedHeaders[k], "test case %d", idx+1)
		}
	}
}

func TestSendInvalidHeader(t *testing.T) {
	srv, _ := testhelper.HTTPWebhookMock()
	defer srv.Close()
	ch := &Channel{
		ChannelName:  "test",
		TemplateFile: "06_template",
		URL:          srv.URL + "/",
		Headers:      []string{"HeaderNoColon"},
		Fail:         true,
	}

	errorChannel := make(chan error)
	defer close(errorChannel)
	go ch.Send(context.TODO(), NotificationValues{}, errorChannel)

	// In particular, Connaisseur did not panic
	assert.Error(t, <-errorChannel)
}

func TestSendError(t *testing.T) {
	var testCases = []struct {
		template    string
		expectedErr string
		calls       int
		urlOverride string
	}{
		{ // 1: Sending of notification fails
			"06_template",
			"failed to send notification",
			0,
			"ptth://localhost:8080",
		},
		{ // 2: Server responds with error code
			"11_fail_template",
			"failed to send notification",
			1,
			"",
		},
		{ // 3: Request is invalid
			"06_template",
			"failed to create request for notification",
			0,
			"in validScheme://some.url",
		},
		{ // 4: Template doesn't exist
			"doesn't_exist",
			"unable to get template file",
			0,
			"",
		},
		{ // 5: Template is empty
			"08_render_err",
			"failed to render template",
			0,
			"",
		},
	}

	for idx, tc := range testCases {
		srv, c := testhelper.HTTPWebhookMock()
		defer srv.Close()

		if tc.urlOverride != "" {
			srv.URL = tc.urlOverride
		}

		ch := &Channel{
			ChannelName:  "test",
			TemplateFile: tc.template,
			URL:          srv.URL + "/",
			Headers:      []string{},
			Fail:         true,
		}

		errorChannel := make(chan error)
		defer close(errorChannel)
		go ch.Send(context.TODO(), NotificationValues{}, errorChannel)
		err := <-errorChannel
		srv.Close()
		assert.NotNil(t, err, "test case %d", idx+1)
		assert.Equal(t, c.Calls, tc.calls, "test case %d", idx+1)
		assert.ErrorContains(t, err, tc.expectedErr, "test case %d", idx+1)
	}
}

func TestSendExpiredContext(t *testing.T) {
	ctx := context.Background()
	ctx, cancel := context.WithCancel(ctx)
	cancel()
	ch := &Channel{Fail: true}
	err := make(chan error)

	ch.Send(ctx, NotificationValues{}, err)

	// We receive no answer (and also don't panic)
	select {
	case <-err:
		assert.Fail(t, "received an unexpected error")
	case <-time.After(time.Second):
	}
}

func TestFailOnError(t *testing.T) {
	var testCases = []struct {
		fail bool
	}{
		{
			true,
		},
		{
			false,
		},
	}

	for idx, tc := range testCases {
		ch := &Channel{Fail: tc.fail}
		assert.Equal(t, tc.fail, ch.FailOnError(), idx+1)
	}
}

func TestName(t *testing.T) {
	ch := &Channel{ChannelName: "test"}
	assert.Equal(t, "test", ch.Name())
}
