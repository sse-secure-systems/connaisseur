package cosignvalidator

import (
	"connaisseur/internal/validator/auth"
	"context"
	"crypto"
	"fmt"
	"strings"

	"github.com/sigstore/cosign/v2/pkg/cosign"
	sigs "github.com/sigstore/cosign/v2/pkg/signature"
	sig "github.com/sigstore/sigstore/pkg/signature"
)

type Verifier struct {
	// name of the trust root
	Name string
	// verifier for the public keys
	KeyVerifier sig.Verifier
	// verifier for keyless signatures
	KeylessVerifier cosign.Identity
}

// Loads a public key from a key inline key or a key reference.
func LoadVerifier(
	ctx context.Context,
	trustRoot auth.TrustRoot,
) (Verifier, error) {
	var (
		keyVerifier     sig.Verifier
		keylessVerifier cosign.Identity
		err             error
	)

	if trustRoot.Key != "" { // explicit public key was given
		hashAlgorithm := crypto.SHA256
		if strings.HasPrefix(trustRoot.Key, "-----BEGIN PUBLIC KEY-----") {
			keyVerifier, err = sigs.LoadPublicKeyRaw([]byte(trustRoot.Key), hashAlgorithm)
		} else {
			keyVerifier, err = sigs.PublicKeyFromKeyRefWithHashAlgo(ctx, trustRoot.Key, hashAlgorithm)
		}
	} else if (trustRoot.Keyless.Issuer != "" || trustRoot.Keyless.IssuerRegex != "") &&
		(trustRoot.Keyless.Subject != "" || trustRoot.Keyless.SubjectRegex != "") { // keyless flow
		keylessVerifier = cosign.Identity{
			// according to cosign implementation, regex wins over non regex
			Issuer:        trustRoot.Keyless.Issuer,
			IssuerRegExp:  trustRoot.Keyless.IssuerRegex,
			Subject:       trustRoot.Keyless.Subject,
			SubjectRegExp: trustRoot.Keyless.SubjectRegex,
		}
	} else {
		err = fmt.Errorf("no public key or keyless configuration found")
	}

	return Verifier{
		Name:            trustRoot.Name,
		KeyVerifier:     keyVerifier,
		KeylessVerifier: keylessVerifier,
	}, err
}
