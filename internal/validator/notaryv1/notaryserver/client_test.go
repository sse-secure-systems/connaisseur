package notaryserver

import (
	"connaisseur/internal/image"
	"connaisseur/internal/validator/auth"
	"connaisseur/test/testhelper"
	"context"
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"net/http"
	"testing"

	"github.com/stretchr/testify/assert"
)

const BASE = "../../../../test/testdata/notaryv1/trust_data"

var (
	notaryClient *NotaryClient
	err          error
)

type MockFailingDoPingClient struct{}

func (client MockFailingDoPingClient) Do(*http.Request) (*http.Response, error) {
	return nil, fmt.Errorf("Do method threw an error.")
}

type MockPingClientRespondingWithoutRequestProperty struct{}

// this should be part of the mock server, but I found no way to tell a *http.ResponseWriter to drop
// the
// request property of the response, so I resorted to creating the response manually
func (client MockPingClientRespondingWithoutRequestProperty) Do(
	req *http.Request,
) (*http.Response, error) {
	resp := &http.Response{
		Status:     "401 Unauthorized",
		StatusCode: 401,
		Proto:      "HTTP/1.0",
		ProtoMajor: 1,
		ProtoMinor: 0,
		Header:     http.Header{},
		Body:       http.NoBody,
		Request:    nil,
		TLS:        nil,
	}

	return resp, nil
}

func mockedFailingDoPingClient(baseTransport *http.Transport) HttpClient {
	return &MockFailingDoPingClient{}
}

func mockedPingClientRespondingWithoutRequestProperty(baseTransport *http.Transport) HttpClient {
	return &MockPingClientRespondingWithoutRequestProperty{}
}

func TestNewNotaryClient(t *testing.T) {
	var testCases = []struct {
		validHost         bool
		cert              string
		getPingClientFunc pingClientGetter
		err               string
	}{
		// happy case, client to srvurl with repo of sample image returned
		{
			true,
			"",
			getPingClient,
			"",
		},
		// invalid notary host url will make NewRequest throw an error due to `urlpkg.Parse(url)`
		// --> request creation error
		{
			false,
			"",
			getPingClient,
			"error creating ping request",
		},
		// invalid cert --> tls config error
		{
			true,
			"aaa",
			getPingClient,
			"error setting up TLS config",
		},
		// uses pingClient with mocked Do method returning an error -> pinging error
		{
			true,
			"",
			mockedFailingDoPingClient,
			"error pinging notary server",
		},
		// uses ping client that responds with an http.Response with a request property, which is
		// the only way to make the adding of a challenge response fail --> add response to
		// challenge manager error
		{
			true,
			"",
			mockedPingClientRespondingWithoutRequestProperty,
			"error adding challenge response",
		},
	}

	srv := testhelper.NotaryMock(BASE, true)
	defer srv.Close()
	img, _ := image.New("sample-image")
	for _, tc := range testCases {
		if tc.validHost == true {
			notaryClient, err = newNotaryClient(
				tc.getPingClientFunc,
				srv.URL,
				tc.cert,
				auth.Auth{},
				img,
			)
		} else {
			notaryClient, err = newNotaryClient(tc.getPingClientFunc, "%%..invalid.URL!", tc.cert, auth.Auth{}, img)
		}
		if tc.err != "" {
			assert.NotNil(t, err)
			assert.ErrorContains(t, err, tc.err)
		} else {
			assert.Nil(t, err)
			assert.Equal(t, srv.URL, notaryClient.host)
			assert.Equal(t, "docker.io/library/sample-image", notaryClient.repo)
		}
	}
}

func TestNewNotaryClientWithoutAuth(t *testing.T) {
	srv := testhelper.NotaryMock(BASE, false)
	defer srv.Close()
	img, _ := image.New("sample-image")
	notaryClient, err = newNotaryClient(getPingClient, srv.URL, "", auth.Auth{}, img)
	assert.Equal(t, "docker.io/library/sample-image", notaryClient.repo)
}

func TestFetchTrustData(t *testing.T) {
	var testCases = []struct {
		image    string
		role     string
		username string
		password string
		sha256   string
		err      string
	}{
		// 1: tests whether root trust data of sample-image
		// (test/testdata/notaryv1/trust_data/sample-image/root.json) is correctly returned
		{
			"sample-image",
			"root",
			"",
			"",
			"76d25d66f45387cce5ac088489a9bf0ac27554da9789098e6c8fdb00856612f7",
			"",
		},
		// 2: tests whether targets trust data of sample-image
		// (test/testdata/notaryv1/trust_data/sample-image/targets.json) is correctly returned
		{
			"sample-image",
			"targets",
			"",
			"",
			"e122a90e80a92c98ff7368d3e90f4c0f23e44df642737e5fede68578b85918c9",
			"",
		},
		// 3: mock server will return "404 Not Found" because there won't be a corresponding file to
		// "there-is-no-image" in the test data folder --> error as status code is not 2**
		{
			"there-is-no-image",
			"targets",
			"",
			"",
			"",
			"error acquiring trust data targets",
		},
		// 4: mock server will return raw bytes of invalid json in
		// test/testdata/notaryv1/trust_data/err-image/invalid.json --> unmarshalling error
		{
			"err-image",
			"invalid",
			"",
			"",
			"",
			"error unmarshalling trust data invalid",
		},
		// 5: The Do method will *throw an error* "Unauthorized" (instead of *responding* with 401)
		// due to username "" and pw "" --> error requesting the trust data
		{
			"alice-image",
			"root",
			"",
			"",
			"",
			"error doing request trust data root",
		},
		// 6: tests whether root trust data of alice-image
		// (test/testdata/notaryv1/trust_data/alice-image/root.json) is correctly returned
		{
			"alice-image",
			"root",
			"test",
			"test",
			"ba73995b5a4a2f61b2dcf5bcd6683bb706b6e64224862d110098e7d2a6147c4e",
			"",
		},
		// 7: role {this€should§makeµURL%%invalid} makes an invalid URL of the endpoint for the
		// role's trust data --> error creating request
		{
			"alice-image",
			"{this€should§makeµURL%%invalid}",
			"test",
			"test",
			"",
			"error creating request for acquiring trust data",
		},
		// 8: role "return-invalid-response-body-please" will let the mock server return an invalid
		// response body --> error reading response body
		{
			"sample-image",
			"return-invalid-response-body-please",
			"test",
			"test",
			"",
			"error reading trust data",
		},
	}

	srv := testhelper.NotaryMock(BASE, true)
	defer srv.Close()

	ctx := context.Background()
	out := make(chan TrustData, 1)
	defer close(out)

	for idx, tc := range testCases {
		img, _ := image.New(tc.image)
		rr, _ := image.NewRegistryRepo(srv.URL)
		notaryClient, err = NewNotaryClient(
			srv.URL,
			"",
			auth.Auth{
				AuthConfigs: map[string]auth.AuthEntry{
					rr.String(): {Username: tc.username, Password: tc.password},
				},
				UseKeychain: false,
			},
			img,
		)
		notaryClient.FetchTrustData(ctx, tc.role, out)
		tr := <-out

		if tc.err != "" {
			assert.NotNil(t, tr.Err, idx+1)
			assert.ErrorContains(t, tr.Err, tc.err, idx+1)
		} else {
			assert.Nil(t, tr.Err, idx+1)
			sha := sha256.Sum256(tr.Raw)
			assert.Equal(t, tc.sha256, hex.EncodeToString(sha[:]), idx+1)
		}
	}
}

func TestTLSConfig(t *testing.T) {
	var testCases = []struct {
		cert string
		err  string
	}{
		// valid cert --> tests valid TLS config is returned
		{
			`-----BEGIN CERTIFICATE-----
MIIEAzCCAuugAwIBAgIQaNovZx6t4Id3+bpP3JZAETANBgkqhkiG9w0BAQsFADA4
MTYwNAYDVQQDEy1yZWxlYXNlLW5hbWUtcHJpdmF0ZS1yZWdpc3RyeS5jb25uYWlz
c2V1ci5zdmMwIBcNMjMwNzE5MDkyNTQ2WhgPMjEyMzA2MjUwOTI1NDZaMDgxNjA0
BgNVBAMTLXJlbGVhc2UtbmFtZS1wcml2YXRlLXJlZ2lzdHJ5LmNvbm5haXNzZXVy
LnN2YzCCASIwDQYJKoZIhvcNAQEBBQADggEPADCCAQoCggEBAJPVASCV0UXXoAE6
3jw4L30GKf9+XkTrJ6hBEEmpoD9dmq7fZirCNQ09fX2P+oFs9aVVSXLBpalOriwg
OgVmDEKXgeAeyt2cTq9XDvfUJ3vOsCyRoTZTmtTNbnvicNpjw8n8k7yTAORD3NAn
tveHYOpjprQxVaXwDJBwX1n0d10KIFINBQSRYhiabEiw0Yqo4QGhq/d/rybS2sZc
bsJANSFhdeQMBAMC2KaGhVtSh2wPHZeu7Ie0/p9onP+sSgAkH516hsXn0BYYAHmB
M9xjwrWOjvhNGth6Uqv+zoDnqpH9x74cEJJpZyyShpP+5o0i4W26pkN4ubUO3v6m
MI7Sf48CAwEAAaOCAQUwggEBMA4GA1UdDwEB/wQEAwIFoDAdBgNVHSUEFjAUBggr
BgEFBQcDAQYIKwYBBQUHAwIwDAYDVR0TAQH/BAIwADCBwQYDVR0RBIG5MIG2gh1y
ZWxlYXNlLW5hbWUtcHJpdmF0ZS1yZWdpc3RyeYIpcmVsZWFzZS1uYW1lLXByaXZh
dGUtcmVnaXN0cnkuY29ubmFpc3NldXKCLXJlbGVhc2UtbmFtZS1wcml2YXRlLXJl
Z2lzdHJ5LmNvbm5haXNzZXVyLnN2Y4I7cmVsZWFzZS1uYW1lLXByaXZhdGUtcmVn
aXN0cnkuY29ubmFpc3NldXIuc3ZjLmNsdXN0ZXIubG9jYWwwDQYJKoZIhvcNAQEL
BQADggEBAIs+pLoykr7/DP1rS4BfgchYUP24lNXsM6Xj2gJhYhdcbtgjW+FG5f2d
YpwvYimBHhNFxxHnOaIEHjxmMI1+nMz9Mh/zJBT/swV1pDG+uoeT4PqjR/B7EXu+
AzzN6VOrJJ3OnlE5x+EuAOTdBBNIfmnsDUO+wgSln0dV3/u7LUBgQaT5hRHf+AQm
Y/6duOanh6ORR5FWASh1W+e8VBbvbWc62c9K7Tbt3CyApMHx1MN7oX+WZ0Klv+Q4
9Q+j464V31M1jEwZc7GHVvSaiXwL89mtjH7s6d9aAQQPtTiQKY8hAgxpzbBnXLcU
YWedcoUI044jFnxGv9P9fHI3LcNTt4I=
-----END CERTIFICATE-----`,
			"",
		},
		// invalid cert --> parse certificate error
		{
			"aaa",
			"failed to parse root certificate",
		},
	}

	for _, tc := range testCases {
		cfg, err := tlsConfig(tc.cert)

		if tc.err != "" {
			assert.NotNil(t, err)
			assert.ErrorContains(t, err, tc.err)
		} else {
			assert.Nil(t, err)
			assert.NotNil(t, cfg)
		}
	}
}
