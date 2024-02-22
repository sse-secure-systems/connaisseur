package notaryserver

import (
	"connaisseur/internal/constants"
	"connaisseur/internal/image"
	auth1 "connaisseur/internal/validator/auth"
	"context"
	"crypto/tls"
	"crypto/x509"
	"encoding/json"
	"fmt"
	"io"
	"net"
	"net/http"
	"time"

	"github.com/docker/distribution/registry/client/auth"
	"github.com/docker/distribution/registry/client/auth/challenge"
	"github.com/docker/distribution/registry/client/transport"
	registrytypes "github.com/docker/docker/api/types/registry"
	"github.com/docker/docker/registry"
	"github.com/docker/go-connections/tlsconfig"
	"github.com/sirupsen/logrus"
	"github.com/theupdateframework/notary/tuf/data"
)

type NotaryClient struct {
	client *http.Client
	host   string
	repo   string
}

type TrustData struct {
	Role string
	Data *data.Signed
	Raw  []byte
	Err  error
}

type HttpClient interface {
	Do(req *http.Request) (*http.Response, error)
}

type pingClientGetter func(*http.Transport) HttpClient

func NewNotaryClient(
	host string,
	cert string,
	authConf auth1.Auth,
	imageRef *image.Image,
) (*NotaryClient, error) {
	return newNotaryClient(getPingClient, host, cert, authConf, imageRef)
}

func newNotaryClient(
	getPingClientFunc pingClientGetter,
	host string,
	cert string,
	authCreds auth1.Auth,
	imageRef *image.Image,
) (*NotaryClient, error) {
	logrus.Debugf("creating new notary client for %s with host %s", imageRef.OriginalString(), host)

	notaryRef := imageRef.NotaryReference()

	// first, just ping the notary instance to see if it's up
	// and acquiring the authentication realm
	req, err := http.NewRequest(http.MethodGet, host+"/v2/", nil)
	if err != nil {
		return nil, fmt.Errorf("error creating ping request: %s", err)
	}

	clientTransport, err := baseTransport(cert)
	if err != nil {
		return nil, fmt.Errorf("unable configuring base transport settings for http client %s", err)
	}

	pingClient := getPingClientFunc(clientTransport)

	resp, err := pingClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("error pinging notary server: %s", err)
	}
	defer resp.Body.Close()

	var roundTripper http.RoundTripper
	if resp.StatusCode == http.StatusUnauthorized {
		challengeManager := challenge.NewSimpleManager()
		if err := challengeManager.AddResponse(resp); err != nil {
			return nil, fmt.Errorf("error adding challenge response: %s", err)
		}
		roundTripper = buildAuthTransport(
			clientTransport,
			host,
			authCreds,
			notaryRef,
			challengeManager,
		)
	} else {
		roundTripper = transport.NewTransport(clientTransport, transport.NewHeaderRequestModifier(http.Header{}))
	}

	// create notary client
	logrus.Debug("creating notary client")
	notaryClient := &http.Client{
		Transport: roundTripper,
		Timeout:   10 * time.Second,
	}

	return &NotaryClient{client: notaryClient, host: host, repo: notaryRef}, nil
}

func getPingClient(baseTransport *http.Transport) HttpClient {
	roundTripper := transport.NewTransport(
		baseTransport,
		transport.NewHeaderRequestModifier(http.Header{}),
	)
	pingClient := &http.Client{
		Transport: roundTripper,
		Timeout:   5 * time.Second,
	}
	return pingClient
}

func baseTransport(cert string) (*http.Transport, error) {
	cfg, err := tlsConfig(cert)
	if err != nil {
		return nil, fmt.Errorf("error setting up TLS config: %s", err)
	}
	base := &http.Transport{
		Dial: (&net.Dialer{
			Timeout:   constants.ValidationTimeoutSeconds * time.Second,
			KeepAlive: constants.ValidationTimeoutSeconds * time.Second,
			DualStack: true,
		}).Dial,
		TLSHandshakeTimeout: constants.TLSHandshakeTimeoutSeconds * time.Second,
		TLSClientConfig:     cfg,
	}

	return base, nil
}

func buildAuthTransport(
	base *http.Transport,
	host string,
	authConf auth1.Auth,
	img string,
	challengeManager challenge.Manager,
) http.RoundTripper {
	// ignore error, because checks were already made
	rr, _ := image.NewRegistryRepo(host)

	// now create authentication transport
	// set everything up for authentication
	authCreds := authConf.LookUp(rr.String())
	scope := auth.RepositoryScope{
		Repository: img,
		Actions:    []string{"pull"},
	}
	creds := simpleCredentialStore{
		auth: registrytypes.AuthConfig{
			Username: authCreds.Username,
			Password: authCreds.Password,
		},
	}
	tokenHandlerOptions := auth.TokenHandlerOptions{
		Transport:   base,
		Credentials: creds,
		Scopes:      []auth.Scope{scope},
		ClientID:    registry.AuthClientID,
	}
	tokenHandler := auth.NewTokenHandlerWithOptions(tokenHandlerOptions)
	basicHandler := auth.NewBasicHandler(creds)
	modifier := auth.NewAuthorizer(challengeManager, tokenHandler, basicHandler)
	return transport.NewTransport(base, modifier)
}

func tlsConfig(cert string) (*tls.Config, error) {
	cfg := tlsconfig.ClientDefault()

	if cert != "" {
		roots := x509.NewCertPool()
		if !roots.AppendCertsFromPEM([]byte(cert)) {
			return nil, fmt.Errorf("failed to parse root certificate")
		}
		cfg.RootCAs = roots
	}

	return cfg, nil
}

func (nc *NotaryClient) FetchTrustData(
	ctx context.Context,
	role string,
	out chan<- TrustData,
) {
	var (
		errOut     error
		signedData *data.Signed
		rawData    []byte
	)

	logrus.Debugf("getting trust data for %s", role)

	defer func() {
		// wait for context to be cancelled or for data to be acquired
		select {
		case <-ctx.Done():
			return
		default:
			out <- TrustData{Role: role, Data: signedData, Raw: rawData, Err: errOut}
			return
		}
	}()

	req, err := http.NewRequest(
		http.MethodGet,
		// host and repo are from the configuration and role is either a base role or inside the
		// required delegations,
		// so neither of these values is "attacker"-controlled and thus the call should be fine
		fmt.Sprintf("%s/v2/%s/_trust/tuf/%s.json", nc.host, nc.repo, role),
		nil,
	)
	if err != nil {
		errOut = fmt.Errorf(
			"error creating request for acquiring trust data %s: %s",
			role,
			err,
		)
		return
	}

	resp, err := nc.client.Do(req)
	if err != nil {
		errOut = fmt.Errorf("error doing request trust data %s: %s", role, err)
		return
	} else {
		defer resp.Body.Close()
		if resp.StatusCode != http.StatusOK {
			errOut = fmt.Errorf(
				"error acquiring trust data %s: %s",
				role,
				resp.Status,
			)
			return
		}

		if data, err := io.ReadAll(resp.Body); err != nil {
			errOut = fmt.Errorf("error reading trust data %s: %s", role, err)
			return
		} else {
			rawData = data
		}
	}

	signed := &data.Signed{}
	if err := json.Unmarshal(rawData, signed); err != nil {
		errOut = fmt.Errorf("error unmarshalling trust data %s: %s", role, err)
		return
	}

	signedData = signed
}
