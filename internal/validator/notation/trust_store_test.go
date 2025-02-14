package notation

import (
	"context"
	"os"
	"testing"

	"github.com/stretchr/testify/assert"
	"gopkg.in/yaml.v3"
)

func TestGetCertificates(t *testing.T) {
	var testCases = []struct {
		file string
		name string
		err  string
	}{
		{ // 1: simple working case
			"01_notation",
			"default",
			"",
		},
		{ // 2: another working case
			"01_notation",
			"cosign-cert",
			"",
		},
		{ // 3: missing trust root
			"01_notation",
			"missing",
			"no certificates found",
		},
	}

	for idx, tc := range testCases {
		var nv NotationValidator

		nvBytes, _ := os.ReadFile(PRE + tc.file + ".yaml")
		yaml.Unmarshal(nvBytes, &nv)

		cert, err := nv.TrustStore.GetCertificates(context.Background(), "", tc.name)

		if tc.err != "" {
			assert.NotNil(t, err, idx+1)
			assert.ErrorContains(t, err, tc.err, idx+1)
		} else {
			assert.Nil(t, err, idx+1)
			assert.NotNil(t, cert, idx+1)
		}
	}
}
