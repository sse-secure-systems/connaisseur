package alerting

import (
	"fmt"
	"testing"

	"github.com/stretchr/testify/assert"
)

var minusOne int = -1

func TestLoadAlertingConfig(t *testing.T) {
	var testCases = []struct {
		alertingFile string
		clusterId    string
		numAdmit     int
		numReject    int
		err          string
	}{
		{ // 1: valid alerting config
			"alerting/00_alerting.yaml",
			"example-cluster-staging-europe",
			2,
			1,
			"",
		},
		{ // 2: unmarshal error in alerting config
			"alerting/01_unmarshal_err.yaml",
			"",
			0,
			0,
			"yaml: unmarshal errors:",
		},
		{ // 3: unmarshal error in request sender
			"alerting/02_requestsender_unmarshal_err.yaml",
			"",
			0,
			0,
			"yaml: unmarshal errors:",
		},
		{ // 4: error sanitizing file path
			"../config/00_sample.yaml",
			"",
			0,
			0,
			"error sanitizing file",
		},
		{ // 5: error loading file
			"alerting/404_notfound.yaml",
			"",
			0,
			0,
			"error sanitizing file",
		},
	}

	for idx, tc := range testCases {
		al, err := LoadConfig(PRE, tc.alertingFile)

		if tc.err != "" {
			assert.Error(t, err, idx+1)
			assert.ErrorContains(t, err, tc.err, idx+1)
		} else {
			assert.NoError(t, err, idx+1)
			assert.Equal(t, tc.clusterId, al.ClusterId, idx+1)
			assert.Len(t, al.AdmitRequests.Receivers, tc.numAdmit, idx+1)
			assert.Len(t, al.RejectRequests.Receivers, tc.numReject, idx+1)

			for i, s := range al.AdmitRequests.Receivers {
				r := s.(*Channel)
				assert.Equal(t, fmt.Sprintf("%s-%d", r.TemplateFile, i), r.ChannelName, idx+1)
			}

			for i, s := range al.RejectRequests.Receivers {
				r := s.(*Channel)
				assert.Equal(t, fmt.Sprintf("%s-%d", r.TemplateFile, i), r.ChannelName, idx+1)
			}
		}
	}
}

func TestValidateErrors(t *testing.T) {
	var testCases = []struct {
		alerting *Config
		err      string
	}{
		{ // 1: no template file
			&Config{
				AdmitRequests: RequestSender{
					Receivers: []Sender{
						&Channel{
							URL: "http://test.com",
						},
					},
				},
			},
			"TemplateFile is a required field",
		},
		{ // 2: no URL
			&Config{
				AdmitRequests: RequestSender{
					Receivers: []Sender{
						&Channel{
							TemplateFile: "test",
						},
					},
				},
			},
			"URL is a required field",
		},
		{ // 3: payload fields must contain at least 1 item
			&Config{
				AdmitRequests: RequestSender{
					Receivers: []Sender{
						&Channel{
							TemplateFile:  "test",
							URL:           "http://test.com",
							PayloadFields: map[string]interface{}{},
						},
					},
				},
			},
			"PayloadFields must contain at least 1 item",
		},
		{ // 4: headers must contain at least 1 item
			&Config{
				AdmitRequests: RequestSender{
					Receivers: []Sender{
						&Channel{
							TemplateFile: "test",
							URL:          "http://test.com",
							Headers:      []string{},
						},
					},
				},
			},
			"Headers must contain at least 1 item",
		},
		{ // 5: headers must contain the text ':'
			&Config{
				AdmitRequests: RequestSender{
					Receivers: []Sender{
						&Channel{
							TemplateFile: "test",
							URL:          "http://test.com",
							Headers:      []string{"test"},
						},
					},
				},
			},
			"Headers[0] must contain the text ':'",
		},
		{
			&Config{
				AdmitRequests: RequestSender{
					Receivers: []Sender{
						&Channel{
							TemplateFile: "test",
							URL:          "http://test.com",
							Priority:     &minusOne,
						},
					},
				},
			},
			"Priority must be 0 or greater",
		},
	}

	for idx, tc := range testCases {
		err := tc.alerting.validate()
		assert.ErrorContains(t, err, tc.err, idx+1)
	}
}
