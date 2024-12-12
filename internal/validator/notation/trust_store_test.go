package notation

import (
	"context"
	"os"
	"testing"

	"github.com/notaryproject/notation-go/verifier/truststore"
	"github.com/stretchr/testify/assert"
	"gopkg.in/yaml.v3"
)

func TestGetCertificates(t *testing.T) {
	var testCases = []struct {
		file  string
		name  string
		type_ string
		err   string
	}{
		{ // 1: simple working case
			"01_notation",
			"default",
			"ca",
			"",
		},
		{ // 2: another working case
			"01_notation",
			"different-cert",
			"ca",
			"",
		},
		{ // 3: missing trust root
			"01_notation",
			"missing",
			"ca",
			"no certificates found",
		},
		{ // 4: normal cert with tsa cert
			"08_tsa_cert",
			"default",
			"ca",
			"",
		},
		{ // 5: tsa cert
			"08_tsa_cert",
			"default",
			"tsa",
			"",
		},
	}

	for idx, tc := range testCases {
		var nv NotationValidator

		nvBytes, _ := os.ReadFile(PRE + tc.file + ".yaml")
		yaml.Unmarshal(nvBytes, &nv)

		cert, err := nv.TrustStore.GetCertificates(
			context.Background(),
			truststore.Type(tc.type_),
			tc.name,
		)

		if tc.err != "" {
			assert.NotNil(t, err, idx+1)
			assert.ErrorContains(t, err, tc.err, idx+1)
		} else {
			assert.Nil(t, err, idx+1)
			assert.NotNil(t, cert, idx+1)
		}
	}
}
