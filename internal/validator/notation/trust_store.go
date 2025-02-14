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
	certs      map[string][]*x509.Certificate
	truststore.X509TrustStore
}

func NewInMemoryTrustStore(trustRoots []auth.TrustRoot) (*InMemoryTrustStore, error) {
	certs := make(map[string][]*x509.Certificate)

	for _, trustRoot := range trustRoots {
		if trustRoot.Cert == "" {
			return &InMemoryTrustStore{}, fmt.Errorf(
				"no certificate provided for trust root %s",
				trustRoot.Name,
			)
		}

		block, _ := pem.Decode([]byte(trustRoot.Cert))
		if block == nil {
			return &InMemoryTrustStore{}, fmt.Errorf(
				"failed to decode certificate for trust root %s",
				trustRoot.Name,
			)
		}

		cert, err := x509.ParseCertificate(block.Bytes)
		if err != nil {
			return &InMemoryTrustStore{}, fmt.Errorf(
				"failed to parse certificate for trust root %s: %w",
				trustRoot.Name,
				err,
			)
		}
		certs[trustRoot.Name] = []*x509.Certificate{cert}
	}

	return &InMemoryTrustStore{
		trustRoots: trustRoots,
		certs:      certs,
	}, nil
}

func (imts *InMemoryTrustStore) GetCertificates(
	ctx context.Context,
	_ truststore.Type,
	namedStore string,
) ([]*x509.Certificate, error) {
	for name, certs := range imts.certs {
		if name == namedStore {
			return certs, nil
		}
	}

	return nil, fmt.Errorf("no certificates found for trustRoot %s", namedStore)
}
