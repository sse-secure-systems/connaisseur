package notaryserver

import (
	"net/url"
	"testing"

	registrytypes "github.com/docker/docker/api/types/registry"
	"github.com/stretchr/testify/assert"
)

func TestSetRefreshToken(t *testing.T) {
	creds := simpleCredentialStore{
		auth: registrytypes.AuthConfig{},
	}
	url := &url.URL{}
	assert.PanicsWithError(t, "function SetRefreshToken is not implemented", func() { creds.SetRefreshToken(url, "", "") })
}
