package cosignvalidator

import (
	"connaisseur/internal/validator/auth"
	"context"
	"crypto/ecdsa"
	"testing"

	"github.com/stretchr/testify/assert"
)

func TestLoadVerifier(t *testing.T) {
	var testCases = []struct {
		trustRoot       auth.TrustRoot
		expPubkey       int64
		expIssuer       string
		expSubject      string
		expIssuerRegex  string
		expSubjectRegex string
		expErr          string
	}{
		{ // 1: working pub key
			auth.TrustRoot{
				Name: "bob",
				Key: `-----BEGIN PUBLIC KEY-----
MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAE01DasuXJ4rfzAEXsURSnbq4QzJ6o
EJ2amYV/CBKqEhhl8fDESxsmbdqtBiZkDV2C3znIwV16SsJlRRYO+UrrAQ==
-----END PUBLIC KEY-----`,
			},
			int64(-7384356341354458600),
			"",
			"",
			"",
			"",
			"",
		},
		{ // 2: working pub key again
			auth.TrustRoot{
				Name: "alice",
				Key: `-----BEGIN PUBLIC KEY-----
MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEusIAt6EJ3YrTHdg2qkWVS0KuotWQ
wHDtyaXlq7Nhj8279+1u/l5pZhXJPW8PnGRRLdO5NbsuM6aT7pOcP100uw==
-----END PUBLIC KEY-----`,
			},
			int64(-3916471775317094451),
			"",
			"",
			"",
			"",
			"",
		},
		{ // 3: working keyless
			auth.TrustRoot{
				Name: "default",
				Keyless: auth.Keyless{
					Issuer:  "issuer",
					Subject: "subject",
				},
			},
			0,
			"issuer",
			"subject",
			"",
			"",
			"",
		},
		{ // 4: empty trust root
			auth.TrustRoot{},
			0,
			"",
			"",
			"",
			"",
			"no public key or keyless configuration found",
		},
		{ // 5: key and keyless
			auth.TrustRoot{
				Name: "default",
				Key: `-----BEGIN PUBLIC KEY-----
MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEusIAt6EJ3YrTHdg2qkWVS0KuotWQ
wHDtyaXlq7Nhj8279+1u/l5pZhXJPW8PnGRRLdO5NbsuM6aT7pOcP100uw==
-----END PUBLIC KEY-----`,
				Keyless: auth.Keyless{
					Issuer:  "issuer",
					Subject: "subject",
				},
			},
			int64(-3916471775317094451),
			"",
			"",
			"",
			"",
			"",
		},
		{ // 7: key error
			auth.TrustRoot{
				Name: "default",
				Key:  "invalid key",
			},
			0,
			"",
			"",
			"",
			"",
			"error parsing public key",
		},
		{ // 8: missing keyless subject
			auth.TrustRoot{
				Name: "default",
				Key:  "",
				Keyless: auth.Keyless{
					Issuer:      "issuer",
					IssuerRegex: "issuer",
				},
			},
			0,
			"",
			"",
			"",
			"",
			"no public key or keyless configuration found",
		},
	}

	for idx, tc := range testCases {
		ctx := context.Background()
		verifier, err := LoadVerifier(ctx, tc.trustRoot)

		if tc.expErr != "" {
			assert.Error(t, err, idx+1)
		} else {
			assert.NoError(t, err, idx+1)
			if tc.expPubkey != 0 {
				pub, _ := verifier.KeyVerifier.PublicKey()
				assert.Equal(t, tc.expPubkey, pub.(*ecdsa.PublicKey).X.Int64(), idx+1)
			}
			assert.Equal(t, tc.expIssuer, verifier.KeylessVerifier.Issuer, idx+1)
			assert.Equal(t, tc.expSubject, verifier.KeylessVerifier.Subject, idx+1)
			assert.Equal(t, tc.expIssuerRegex, verifier.KeylessVerifier.IssuerRegExp, idx+1)
			assert.Equal(t, tc.expSubjectRegex, verifier.KeylessVerifier.SubjectRegExp, idx+1)
		}
	}
}
