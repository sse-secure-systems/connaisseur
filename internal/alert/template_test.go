package alerting

import (
	"encoding/json"
	"testing"

	"github.com/stretchr/testify/assert"
)

const PRE = "../../test/testdata/alerts/"

func TestTransformTemplate(t *testing.T) {
	var testCases = []struct {
		template string
		expected string
		err      string
	}{
		{ // 1: simple working case
			"06_template",
			`{
    "name": "connaisseur_pod_id",
    "value": "{{ .ConnaisseurPodId }}"
}`,
			"",
		},
		{ // 2: working case
			"07_opsgenie",
			`{
    "message": "{{ .AlertMessage }}",
    "alias": "{{ .AlertMessage }} while deploying the images {{ .Images }}.",
    "description": "{{ .AlertMessage }} while deploying the following images:\n {{ .Images }} \n\n Please check the logs of the ` + "`{{ .ConnaisseurPodId }}`" + ` for more details.",
    "responders": [],
    "visibleTo": [],
    "actions": [],
    "tags": [],
    "details": {
        "pod": "{{ .ConnaisseurPodId }}",
        "cluster": "{{ .Cluster }}",
        "namespace": "{{ .Namespace }}",
        "alert_created": "{{ .Timestamp }}",
        "request_id": "{{ .RequestId }}"
    },
    "entity": "Connaisseur",
    "priority": "P{{ .Priority }}"
}`,
			"",
		},
		{ // 3: error case
			"404_notfound",
			"",
			"no such file or directory",
		},
		{ // 4
			"14_triple_bracket",
			`{
    "prio": "{{{ .Priority }}}"
}`,
			"",
		},
		{ // 5
			"15_mismatch_bracket",
			`{
    "prio": "{{{ .Priority }}"
}`,
			"",
		},
		{ // 6
			"16_single_bracket",
			`{
    "prio": "{ priority }"
}`,
			"",
		},
	}

	for idx, tc := range testCases {
		actual, err := transformTemplate(tc.template)

		if tc.err != "" {
			assert.ErrorContains(t, err, tc.err, idx+1)
		} else {
			assert.NoError(t, err, idx+1)
			assert.Equal(t, tc.expected, actual, idx+1)
		}
	}
}

func TestUpdateTemplateWithPayloadFields(t *testing.T) {
	var testCases = []struct {
		template      string
		payloadFields map[string]interface{}
		expected      string
	}{
		{
			"07_opsgenie",
			map[string]interface{}{
				"responders": []string{"test"},
				"visibleTo":  []string{"test"},
				"tags":       []string{"test"},
			},
			`{"actions":[],"alias":"{{ .AlertMessage }} while deploying the images {{ .Images }}.","description":"{{ .AlertMessage }} while deploying the following images:\n {{ .Images }} \n\n Please check the logs of the ` + "`{{ .ConnaisseurPodId }}`" + ` for more details.","details":{"alert_created":"{{ .Timestamp }}","cluster":"{{ .Cluster }}","namespace":"{{ .Namespace }}","pod":"{{ .ConnaisseurPodId }}","request_id":"{{ .RequestId }}"},"entity":"Connaisseur","message":"{{ .AlertMessage }}","priority":"P{{ .Priority }}","responders":["test"],"tags":["test"],"visibleTo":["test"]}`,
		},
	}

	for idx, tc := range testCases {
		tmplStr, _ := transformTemplate(tc.template)
		tmpl := map[string]interface{}{}
		json.Unmarshal([]byte(tmplStr), &tmpl)

		actual := templateWithPayloadFields(tmpl, tc.payloadFields)
		actualByte, _ := json.Marshal(actual)

		assert.Equal(t, tc.expected, string(actualByte), idx+1)
	}
}
