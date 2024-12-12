package auth

import "fmt"

type TrustRoot struct {
	// name of the trust root
	Name string `yaml:"name" validate:"required"`
	// public key of the trust root. either
	// inline key or kms reference
	Key string `yaml:"key" validate:"required_without_all=Cert Keyless,excluded_with=Cert Keyless,omitempty"`
	// certificate of the trust root (notation)
	Cert string `yaml:"cert" validate:"required_without_all=Key Keyless,excluded_with=Key Keyless,omitempty"`
	// timestamp certificate of the trust root (notation)
	TSCert string `yaml:"tsCert" validate:"omitempty"`
	// keyless configuration
	Keyless Keyless `yaml:"keyless" validate:"required_without_all=Key Cert,excluded_with=Key Cert,omitempty"`
}

type Keyless struct {
	// issuer of the trust root (e.g. an oidc provider)
	Issuer string `yaml:"issuer" validate:"required_without=IssuerRegex,excluded_with=IssuerRegex"`
	// subject of the trust root (e.g. a mail address)
	Subject string `yaml:"subject" validate:"required_without=SubjectRegex,excluded_with=SubjectRegex"`
	// issuer regex of the trust root (e.g. an oidc provider)
	IssuerRegex string `yaml:"issuerRegex" validate:"required_without=Issuer,excluded_with=Issuer"`
	// subject regex of the trust root (e.g. a mail address)
	SubjectRegex string `yaml:"subjectRegex" validate:"required_without=Subject,excluded_with=Subject"`
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
