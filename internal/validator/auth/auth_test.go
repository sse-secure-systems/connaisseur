package auth

import (
	"connaisseur/internal/constants"
	"connaisseur/internal/image"
	"os"
	"testing"

	"github.com/stretchr/testify/assert"
	"gopkg.in/yaml.v3"
)

func TestMain(m *testing.M) {
	constants.SecretsDir = "../../../test/testdata/auth/"
	os.Exit(m.Run())
}

func TestAuth(t *testing.T) {
	var testCases = []struct {
		file        string
		authConfigs map[string]AuthEntry
		keyChain    bool
	}{
		{ // 1: default auth file
			"01_auth",
			map[string]AuthEntry{"registry.example.com": {"user", "pass"}},
			false,
		},
		{ // 2: keychain only
			"02_keychain",
			map[string]AuthEntry{},
			true,
		},
		{ // 3: empty auth file
			"03_empty",
			map[string]AuthEntry{},
			false,
		},
		{ // 4: docker auth file
			"08_docker_auth",
			map[string]AuthEntry{
				"index.docker.io":  {"docker", "docker"},
				"registry.io":      {"user", "pass"},
				"registry.io/path": {"test", "test"},
			},
			false,
		},
		{ // 5: default auth file and keychain
			"09_auth_and_keychain",
			map[string]AuthEntry{"registry.example.com": {"user", "pass"}},
			false,
		},
		{ // 6: multiple auth files, default auth file wins
			"10_multi_auth_files",
			map[string]AuthEntry{"registry.example.com": {"user", "pass"}},
			false,
		},
		{ // 7: no registry given
			"13_no_registry_auth",
			map[string]AuthEntry{"EMPTYAUTH": {"user", "pass"}},
			false,
		},
	}

	for idx, tc := range testCases {
		var auth Auth

		authBytes, _ := os.ReadFile(constants.SecretsDir + tc.file + ".yaml")
		err := yaml.Unmarshal(authBytes, &auth)

		assert.Nil(t, err, idx+1)
		assert.Equal(t, len(tc.authConfigs), len(auth.AuthConfigs), idx+1)

		for k, v := range tc.authConfigs {
			assert.Equal(t, v.Username, auth.AuthConfigs[k].Username, idx+1)
			assert.Equal(t, v.Password, auth.AuthConfigs[k].Password, idx+1)
		}

		assert.Equal(t, tc.keyChain, auth.UseKeychain, idx+1)
	}
}

func TestAuthError(t *testing.T) {
	var testCases = []struct {
		file     string
		errorMsg string
	}{
		{ // 1: secretName file not found
			"04_unable_to_find",
			"no authentication file for secret",
		},
		{ // 2: secretName file has invalid format
			"05_err_reading_secret",
			"error reading authentication file",
		},
		{ // 3: auth file has invalid format
			"06_unmarshal_err",
			"unmarshal error",
		},
		{ // 4: no secretName or keychain field defined
			"07_no_secret",
			"neither secretName nor useKeychain defined",
		},
		{ // 5: no secret files
			"11_no_auth_files",
			"no authentication file for secret",
		},
		{ // 6: invalid secret file name
			"12_invalid_secret_file",
			"no authentication file for secret",
		},
		{ // 7: dockerconfigjson with invalid registry
			"14_invalid_registry_docker_auth",
			"unable to parse registry",
		},
	}

	for idx, tc := range testCases {
		var auth Auth

		authBytes, _ := os.ReadFile(constants.SecretsDir + tc.file + ".yaml")
		err := yaml.Unmarshal(authBytes, &auth)

		assert.NotNil(t, err, idx+1)
		assert.ErrorContains(t, err, tc.errorMsg, idx+1)
	}
}

func TestLookUp(t *testing.T) {
	var testCases = []struct {
		file string
		img  string
		user string
		pass string
	}{
		{ // 1: working case
			"08_docker_auth",
			"registry.io/image:tag",
			"user",
			"pass",
		},
		{ // 2: working case
			"08_docker_auth",
			"redis",
			"docker",
			"docker",
		},
		{ // 3: no registry defined
			"08_docker_auth",
			"k8s.io/coredns",
			"",
			"",
		},
		{ // 4: more specific registry defined
			"08_docker_auth",
			"registry.io/path/image:tag",
			"test",
			"test",
		},
	}

	for idx, tc := range testCases {
		var auth Auth

		i, _ := image.New(tc.img)
		authBytes, _ := os.ReadFile(constants.SecretsDir + tc.file + ".yaml")
		_ = yaml.Unmarshal(authBytes, &auth)
		ae := auth.LookUp(i.Context().String())

		assert.Equal(t, tc.user, ae.Username, idx+1)
		assert.Equal(t, tc.pass, ae.Password, idx+1)
	}
}
