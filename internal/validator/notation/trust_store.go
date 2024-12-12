package notation

import (
	"connaisseur/internal/validator/auth"
	"context"
	"crypto/x509"
	"encoding/pem"
	"fmt"

	"github.com/notaryproject/notation-go/verifier/truststore"
)

type TrustStoreKey struct {
	name  string
	type_ truststore.Type
}

type InMemoryTrustStore struct {
	trustRoots []auth.TrustRoot
	certs      map[TrustStoreKey][]*x509.Certificate
	truststore.X509TrustStore
}

func NewInMemoryTrustStore(trustRoots []auth.TrustRoot) (*InMemoryTrustStore, error) {
	certs := make(map[TrustStoreKey][]*x509.Certificate)

	for _, trustRoot := range trustRoots {
		if trustRoot.Cert == "" {
			return &InMemoryTrustStore{}, fmt.Errorf(
				"no certificate provided for trust root %s",
				trustRoot.Name,
			)
		}

		cert, err := parseCertificate(trustRoot.Cert)
		if err != nil {
			return &InMemoryTrustStore{}, fmt.Errorf(
				"failed to parse certificate for trust root %s: %w",
				trustRoot.Name,
				err,
			)
		}
		certs[TrustStoreKey{name: trustRoot.Name, type_: truststore.TypeCA}] = []*x509.Certificate{
			cert,
		}

		// add timestamp cert, if present
		if trustRoot.TSCert != "" {
			tsCert, err := parseCertificate(trustRoot.TSCert)
			if err != nil {
				return &InMemoryTrustStore{}, fmt.Errorf(
					"failed to parse timestamp certificate for trust root %s: %w",
					trustRoot.Name,
					err,
				)
			}
			certs[TrustStoreKey{name: trustRoot.Name, type_: truststore.TypeTSA}] = []*x509.Certificate{
				tsCert,
			}
		}
	}

	return &InMemoryTrustStore{
		trustRoots: trustRoots,
		certs:      certs,
	}, nil
}

func parseCertificate(cert string) (*x509.Certificate, error) {
	block, _ := pem.Decode([]byte(cert))
	if block == nil {
		return nil, fmt.Errorf("failed to decode certificate")
	}

	certParsed, err := x509.ParseCertificate(block.Bytes)
	if err != nil {
		return nil, fmt.Errorf("failed to parse certificate: %w", err)
	}

	return certParsed, nil
}

func (imts *InMemoryTrustStore) GetCertificates(
	ctx context.Context,
	type_ truststore.Type,
	namedStore string,
) ([]*x509.Certificate, error) {
	for tsk, certs := range imts.certs {
		if tsk.name == namedStore && tsk.type_ == type_ {
			return certs, nil
		}
	}

	return nil, fmt.Errorf("no certificates found for trustRoot %s", namedStore)
}
