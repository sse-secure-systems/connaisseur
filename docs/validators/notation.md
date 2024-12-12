# Notation

[Notation](https://github.com/notaryproject/notation) is a [CNCF](https://www.cncf.io/) project that provides a standard for signing and verifying container images and other OCI artifacts using digital signatures.
It is part of the [Notary Project](https://notaryproject.dev/), also known as Notary V2, which builds upon lessons learned from the original Notary (V1) project.
Notation provides a simple command-line experience for signing OCI artifacts and a set of libraries for integration into larger systems.

Unlike Notary V1 which relies on The Update Framework (TUF), Notation uses a simpler trust model based on X.509 certificates and certificate chains.
This makes it easier to integrate with existing PKI infrastructure and certificate management systems.
Signatures are stored as OCI artifacts in the same registry as the signed container images, eliminating the need for a separate trust server.

Connaisseur supports validating Notation signatures based on X.509 certificates configured as trust roots.
The validator can verify signatures created by the Notation CLI or any compatible signing tools that implement the Notation specification.

## Basic usage

To get started with Notation, you'll need to install the Notation CLI and create signing certificates.
The [Notation documentation](https://notaryproject.dev/docs/) provides comprehensive guidance for installation and setup.

### Creating certificates

For testing purposes, you can create a self-signed certificate:

```bash
# Create a self-signed certificate
notation cert generate-test --default "mykey"
```

### Signing images

Once you have certificates configured, you can sign and push container images:

```bash
# Push the image
docker image push <IMAGE_URI>

# Sign with a specific certificate
notation sign --key "mykey" <IMAGE_URI>
```

### Creating trust policy

Before verifying the container image, create a trust policy to match certain images to their respective keys, used for verification.

Create a JSON file with your trust policy:

```bash
cat <<EOF > ./trustpolicy.json
{
    "version": "1.0",
    "trustPolicies": [
        {
            "name": "my-images",
            "registryScopes": [ "*" ],
            "signatureVerification": {
                "level" : "strict"
            },
            "trustStores": [ "ca:mykey" ],
            "trustedIdentities": [
                "*"
            ]
        }
    ]
}
EOF
```

Use `notation policy import` to import the policy:

```bash
notation policy import ./trustpolicy.json
```

### Verifying signatures

You can verify signatures using the Notation CLI:

```bash
# Verify an image signature
notation verify <IMAGE_URI>
```

### Configuring Connaisseur

To use Connaisseur with Notation, configure a validator in `charts/connaisseur/values.yaml` with your signing certificate as a trust root.
The entry in `.application.validators` should look like this:

```yaml title="charts/connaisseur/values.yaml"
- name: mynotation
  type: notation
  trustRoots:
    - name: default
      cert: |
        -----BEGIN CERTIFICATE-----
        MIIDrjCCApagAwIBAgIUfA/t/J6eINSu566aAozkOjQKey4wDQYJKoZIhvcNAQEL
        BQAwbDELMAkGA1UEBhMCREUxDzANBgNVBAgMBkJlcmxpbjEPMA0GA1UEBwwGQmVy
        # ... rest of your certificate ...
        -----END CERTIFICATE-----
```

In `.application.policy`, add a pattern to match your repository:

```yaml title="charts/connaisseur/values.yaml"
- pattern: "docker.io/myrepo/*:*"  # YOUR REPOSITORY
  validator: mynotation
```

After installation, Connaisseur will verify your images against the configured certificates:

```bash
helm install connaisseur helm --atomic --create-namespace --namespace connaisseur
```

### Testing validation

You can test the validation by deploying pods with signed and unsigned images:

```bash
# This should succeed if the image is properly signed
kubectl run signed-app --image=docker.io/myrepo/myimage:signed

# This should fail if the image is not signed or signed with a different certificate
kubectl run unsigned-app --image=docker.io/myrepo/myimage:unsigned
```

## Configuration options

`.application.validators[*]` in `charts/connaisseur/values.yaml` supports the following keys for Notation (refer to [basics](../basics.md#validators) for more information on default keys):

| Key | Default | Required | Description |
| - | - | - | - |
| `name` | - | :heavy_check_mark: | See [basics](../basics.md#validators). |
| `type` | - | :heavy_check_mark: | `notation`; the validator type must be set to `notation`. |
| `trustRoots[*].name` | - | :heavy_check_mark: | See [basics](../basics.md#validators). |
| `trustRoots[*].cert` | - | :heavy_check_mark: | X.509 certificate in PEM format used for signature verification. This should be the root signing certificate or a trusted CA certificate. |
| `trustRoots[*].tsCert` | - | - | X.509 certificate in PEM format used for timestamp countersignature verification. |
| `auth.` | - | - | Authentication credentials for registries with restricted access (e.g., private registries or rate limiting). See additional notes [below](#authentication). |
| `auth.secretName` | - | - | Name of a Kubernetes secret in Connaisseur namespace that contains [dockerconfigjson](https://kubernetes.io/docs/concepts/configuration/secret/#docker-config-secrets) for registry authentication. See additional notes [below](#dockerconfigjson). |
| `cert` | - | - | A TLS certificate in PEM format for private registries with self-signed certificates. |

`.application.policy[*]` in `charts/connaisseur/values.yaml` supports the following additional keys for Notation (refer to [basics](../basics.md#image-policy) for more information on default keys):

| Key | Default | Required | Description |
| - | - | - | - |
| `with.verificationLevel` | `strict` | - | Verification level: `strict`, `permissive`, or `audit`. See additional notes [below](#verification-levels). |
| `with.verifyTimestamp` | `always` | - | Timestamp verification mode: `always`, or `afterCertExpiry`. Only takes effect if `tsCert` is set. See additional notes [below](#timestamp-verification). |

### Example

Since [bitnami signs all their images using notation](https://community.broadcom.com/blogs/carlos-rodriguez-hernandez/2025/01/14/bitnami-packaged-containers-and-helm-charts-in-doc), you can add their public root certificate to Connaisseur and use it to validate all their images:

??? abstract "charts/connaisseur/values.yaml"
    ```yaml title="charts/connaisseur/values.yaml"
    application:
      validators:
      - name: bitnami_notation
        type: notation
        trustRoots:
        - name: bitnami
          cert: |
            -----BEGIN CERTIFICATE-----
            MIIGdDCCBFygAwIBAgIUDBaWhJB62sRxczoYu1AcuyKzx9gwDQYJKoZIhvcNAQEL
            BQAwdjELMAkGA1UEBhMCVVMxFTATBgNVBAoMDFZNd2FyZSwgSW5jLjEjMCEGA1UE
            CwwaVk13YXJlIEFwcGxpY2F0aW9uIENhdGFsb2cxKzApBgNVBAMMIlZNd2FyZSBB
            cHBsaWNhdGlvbiBDYXRhbG9nIFJvb3QgQ0EwHhcNMjMxMTA2MTUzMDM0WhcNNDMx
            MTAyMTUzMDM0WjB2MQswCQYDVQQGEwJVUzEVMBMGA1UECgwMVk13YXJlLCBJbmMu
            MSMwIQYDVQQLDBpWTXdhcmUgQXBwbGljYXRpb24gQ2F0YWxvZzErMCkGA1UEAwwi
            Vk13YXJlIEFwcGxpY2F0aW9uIENhdGFsb2cgUm9vdCBDQTCCAiIwDQYJKoZIhvcN
            AQEBBQADggIPADCCAgoCggIBAKa8IGkj5z0TDXV0MmHOBpCcl+Prnr+PR1qM44O5
            tJtw0Uniaka3Vttp4E+M5rbKqjd/neWwClaJWT3Fg2HC7vi4G0QhauZiuaob4hBc
            2DSPJd7/x3T+CIvu6CC3gCLcMJCEYE5mBoCFEiDeiqlHHzf4SI2e6RFJtv+dC7Oc
            Jj7BgccZvZXHeL4qHQs+zGU/oGyK+Iwn7mHnJp8rmDEHaHTbtXDeTqbxcPPJurDT
            trAW/HfrohCoRMZuZBBgf9s876XgoNz8b8FIQksA8OOTgLQdgDaqDAql+ddZzsrk
            l7VhFkztpinrynKpiz2FtlNfOaaD6rq3hpvbYMe3LkJdqw9cr64H2qGf1/Lx+SEh
            rxBwCcs1tmD8LfK4X1Io4JBDMmwfwZ70NdNqxmCxp6y03F52tAhr1DjvEPVXmBgL
            qdPdmpjNMFgPcjMniTBUfQczsy7UNDlmIUvEVNUQISP3KYFJFV4UOWZ+Kpdf1UPY
            95r/JPlRgJKVQ973EvUPlDkSAlY476L46C+jpZNUf6qm352Mf/VMhoSvAXKCYEzj
            WCf46x4nVRCXTR+StapUy5Ru5Azeo0/BXxTErtHatvGA8+igHD4Sn98MiHDO7gXt
            G9eBzIFPx3jyOIQPFhwujHR+8jA/Y9Z5k3T5C6VNpVRZGG7kW3p5gYCM5yq9cCyB
            tm7nAgMBAAGjgfkwgfYwHQYDVR0OBBYEFA22F2MbRn7kx4J5/ZppgpvCKBqhMIGz
            BgNVHSMEgaswgaiAFA22F2MbRn7kx4J5/ZppgpvCKBqhoXqkeDB2MQswCQYDVQQG
            EwJVUzEVMBMGA1UECgwMVk13YXJlLCBJbmMuMSMwIQYDVQQLDBpWTXdhcmUgQXBw
            bGljYXRpb24gQ2F0YWxvZzErMCkGA1UEAwwiVk13YXJlIEFwcGxpY2F0aW9uIENh
            dGFsb2cgUm9vdCBDQYIUDBaWhJB62sRxczoYu1AcuyKzx9gwDwYDVR0TAQH/BAUw
            AwEB/zAOBgNVHQ8BAf8EBAMCAYYwDQYJKoZIhvcNAQELBQADggIBAGOdQSsRNipU
            dZIL/K5fqbgjdYwafpgdjF8z1r9yLKWIEuCCiQFqRZ1CzjnP4jnIlYJXqvqpwklA
            AE56ZNvjo4LzOkElA4emEa+GmLSQ4CqXn+iwX1DYwkyVP7rgZ+k8kjSFjIF2rDhz
            dqnqHA1eyUyb3PhmDFY2694bhWv7D76MzGKLZOFBg3ar0khQp5VaI/bHW1nALAAd
            paM7uAQW/6I20McETtON0weCvbTuljuIVGADLOGwQwjsn7kHbrldEr0EIbtdiEPb
            2Ohis50tPyfrtKVKP/gZBsyTHMaiYxkiNacEDB+cdeDi6kH1Vmm3EFSXWX3vs30D
            3A8AnXw6L7YbXk4PnRy2ueIrs6bya5B9PSzbA2+gEzGnWpZsZmo85DmgpulSSOCM
            lzsP/72ikru888yR0Mvf6BgGestpuXfSSNqUYUTcZVwetyMx/1UC1yCapLJN6eu4
            0oPiQGhSv2uyu6070ne4kXkZL+DYQIjIzqUhS+4AFhBM7drKpo/9gWtHrTq4NRI1
            Q5mnf3lzlPxKV8Uyu2LzdwGb7ySFogAH5/1BGwWVbJvuV+GozJ/AzoPGsNE7mRHu
            ijySwgpMy1PoslxC6UhAeY6IdzoqS1PPQzinknikc4XvG7GLZUwtTooOyHx/ofQo
            RlcLAokhium7GrRC8aceTPeaZHW1+ewh
            -----END CERTIFICATE-----

      policy:
      - pattern: "bitnami/*:*"
        validator: bitnami_notation
        with:
          trustRoot: bitnami
    ```

## Additional notes

### Authentication

When using private registries, you need to provide authentication credentials to Connaisseur.

#### dockerconfigjson

Create a [dockerconfigjson](https://kubernetes.io/docs/concepts/configuration/secret/#docker-config-secrets) Kubernetes secret in the Connaisseur namespace and pass the secret name to Connaisseur as `auth.secretName`.

The secret can be created from your local Docker configuration:

```bash
kubectl create secret generic my-registry-secret \
  --from-file=.dockerconfigjson=$HOME/.docker/config.json \
  --type=kubernetes.io/dockerconfigjson \
  -n connaisseur
```

Or created directly from credentials:

```bash
kubectl create secret docker-registry my-registry-secret \
  --docker-server=myregistry.com \
  --docker-username=myuser \
  --docker-password=mypassword \
  --docker-email=myemail@example.com \
  -n connaisseur
```

### Verification levels

Notation supports different verification levels:

- **strict** (default): Enforces all validations (integrity, authenticity, authentic timestamp, expiry, revocation check).
- **permissive**: Enforces validation on integrity and authenticity, but will only log failures for revocation and expiry.
- **audit**: Only enforces integrity, logs all the rest.

For more details see the [trust store policy spec](https://github.com/notaryproject/specifications/blob/main/specs/trust-store-trust-policy.md#signature-verification-details).

### Timestamp verification

Notation can verify timestamps in signatures to ensure they were created when the signing certificate was valid:

- **always** (default): Always verify timestamps if present.
- **afterCertExpiry**: Only verify timestamps after the signing certificate has expired.

For more details see the [trust store policy spec](https://github.com/notaryproject/specifications/blob/main/specs/trust-store-trust-policy.md#version-10).

Be aware that the timestamp verification only takes effect if a timestamp certificate is provided. Otherwise the option is ignored.
