package auth

import (
	"connaisseur/internal/constants"
	"connaisseur/internal/image"
	"connaisseur/internal/utils"
	"fmt"
	"os"
	"strings"

	"github.com/docker/cli/cli/config/configfile"
	"github.com/sirupsen/logrus"
	"gopkg.in/yaml.v3"
)

type Auth struct {
	// AuthConfigs is a map of registry URL patterns to authentication credentials.
	AuthConfigs map[string]AuthEntry `validate:"omitempty,min=1,dive,keys,required,endkeys,required"`
	// UseKeychain indicates whether the kubernetes keychain should be used to
	UseKeychain bool
}

type AuthEntry struct {
	Username string
	Password string
}

func (a *Auth) UnmarshalYAML(unmarshal func(interface{}) error) error {
	var vdata map[string]interface{}
	if err := unmarshal(&vdata); err != nil {
		return err
	}

	// if a validator uses authentication, there will always be a secretName,
	// since a username + password are replaced with a newly generated
	// secret in the chart during installation. the secretName will always
	// point to a local file.
	sn, ok1 := vdata["secretName"]
	kc, ok2 := vdata["useKeychain"]

	if ok1 {
		secretName := sn.(string)

		// there is either a "secret.yaml" or ".dockerconfigjson" file.
		// whichever is found first, is used and read for its credentials.
		cases := []struct {
			fileName     string
			readFunction func(string) (map[string]AuthEntry, error)
		}{
			{constants.DefaultAuthFile, readDefaultAuthFile},
			{constants.DockerAuthFile, readDockerAuthFile},
		}

		for _, c := range cases {
			// SafeFileName will return an error if the file does not exist (since Symlinks are
			// evaluated).
			file, err := utils.SafeFileName(constants.SecretsDir, secretName, c.fileName)
			if err == nil {
				a.AuthConfigs, err = c.readFunction(file)
				if err != nil {
					return fmt.Errorf("error reading authentication file %s: %s", file, err)
				}
				return nil
			}
		}

		return fmt.Errorf("no authentication file for secret %s", secretName)
	} else if ok2 {
		a.UseKeychain = kc.(bool)
	} else {
		return fmt.Errorf("neither secretName nor useKeychain defined")
	}

	return nil
}

func readDefaultAuthFile(filePath string) (map[string]AuthEntry, error) {
	secretBytes, err := os.ReadFile(filePath) // #nosec G304
	if err != nil {
		return nil, fmt.Errorf("unable to read secret %s: %s", filePath, err)
	}

	var af = struct {
		Username string `yaml:"username"`
		Password string `yaml:"password"`
		Registry string `yaml:"registry"`
	}{}
	if err = yaml.Unmarshal(secretBytes, &af); err != nil {
		return nil, err
	}

	// registry is optional for nv1 validators, thus the default is set and
	// potentially rewritten in the UnmarshalYAML function of the nv1 validator
	if af.Registry == "" {
		af.Registry = constants.EmptyAuthRegistry
	}

	rr, err := image.NewRegistryRepo(af.Registry)
	if err != nil {
		return nil, fmt.Errorf("unable to parse registry %s: %s", af.Registry, err)
	}

	return map[string]AuthEntry{
		rr.String(): {
			Username: af.Username,
			Password: af.Password,
		},
	}, nil
}

func readDockerAuthFile(filePath string) (map[string]AuthEntry, error) {
	authCfgs := map[string]AuthEntry{}

	secretFile, err := os.Open(filePath) // #nosec G304
	if err != nil {
		return nil, err
	}

	cfg := configfile.New(filePath)
	if err := cfg.LoadFromReader(secretFile); err != nil {
		return nil, err
	}

	for key, value := range cfg.AuthConfigs {
		rr, err := image.NewRegistryRepo(key)
		if err != nil {
			return nil, fmt.Errorf("unable to parse registry %s: %s", key, err)
		}

		authCfgs[rr.String()] = AuthEntry{
			Username: value.Username,
			Password: value.Password,
		}
	}

	return authCfgs, nil
}

func (a *Auth) LookUp(img string) AuthEntry {
	bestHit := ""

	for k := range a.AuthConfigs {
		if len(k) > len(bestHit) {
			if strings.HasPrefix(img, k) {
				bestHit = k
			}
		}
	}

	if bestHit != "" {
		return a.AuthConfigs[bestHit]
	}

	// only warn if there are actually credentials defined
	if len(a.AuthConfigs) > 0 {
		logrus.Warnf("no credentials found for %s", img)
	}

	return AuthEntry{}
}
