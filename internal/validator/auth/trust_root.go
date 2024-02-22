package auth

import "fmt"

type TrustRoot struct {
	// name of the trust root
	Name string `yaml:"name" validate:"required"`
	// public key of the trust root. either
	// inline key or kms reference
	Key string `yaml:"key" validate:"required_without=Cert,excluded_with=Cert"`
	// certificate of the trust root (notaryv2)
	Cert string `yaml:"cert" validate:"required_without=Key,excluded_with=Key"`
}

// Returns the trust roots for the given key references matching
// on the trust roots names. If no key references are given
// and useDefaultValue is true, the trust root named "default"
// is returned.
func GetTrustRoots(
	keyRefs []string,
	trustRoots []TrustRoot,
	useDefaultValue bool,
) ([]TrustRoot, error) {
	trustRootsKeys := []TrustRoot{}

	noKeyRefProvided := len(keyRefs) == 0 || (len(keyRefs) == 1 && keyRefs[0] == "")
	if noKeyRefProvided && useDefaultValue {
		keyRefs = []string{"default"}
	}

	for idx, keyRef := range keyRefs {
		if keyRef == "*" && len(keyRefs) == 1 {
			return trustRoots, nil
		} else {
			for _, tr := range trustRoots {
				if tr.Name == keyRef {
					trustRootsKeys = append(trustRootsKeys, tr)
					break
				}
			}
		}

		if len(trustRootsKeys) < idx+1 {
			return nil, fmt.Errorf("unable to find trust root %s", keyRef)
		}
	}

	if len(trustRootsKeys) == 0 {
		return nil, fmt.Errorf("no trust roots defined for key references %s", keyRefs)
	}

	return trustRootsKeys, nil
}
