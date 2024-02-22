package notaryserver

import (
	"fmt"
	"net/url"

	"github.com/docker/docker/api/types/registry"
)

type simpleCredentialStore struct {
	auth registry.AuthConfig
}

func (scs simpleCredentialStore) Basic(*url.URL) (string, string) {
	return scs.auth.Username, scs.auth.Password
}

func (scs simpleCredentialStore) RefreshToken(*url.URL, string) string {
	return scs.auth.IdentityToken
}

func (scs simpleCredentialStore) SetRefreshToken(*url.URL, string, string) {
	panic(fmt.Errorf("function SetRefreshToken is not implemented"))
}
