package notation

import (
	"connaisseur/internal/validator/auth"
	"context"
	"crypto/x509"
	"encoding/pem"
	"fmt"

	"github.com/notaryproject/notation-go/verifier/truststore"
)

type InMemoryTrustStore struct {
	trustRoots []auth.TrustRoot
	truststore.X509TrustStore
}

func (imts *InMemoryTrustStore) GetCertificates(
	ctx context.Context,
	_ truststore.Type,
	namedStore string,
) ([]*x509.Certificate, error) {
	var certs []*x509.Certificate

	for _, trustRoot := range imts.trustRoots {
		if trustRoot.Name == namedStore {
			block, _ := pem.Decode([]byte(trustRoot.Cert))
			cert, err := x509.ParseCertificate(block.Bytes)
			if err != nil {
				return nil, fmt.Errorf(
					"failed to parse certificate for trustRoot %s: %s",
					trustRoot.Name,
					err,
				)
			}
			certs = append(certs, cert)
		}
	}

	return certs, nil
}
