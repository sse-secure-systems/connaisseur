# sigstore / Cosign

[sigstore](https://sigstore.dev/) is a [Linux Foundation](https://linuxfoundation.org/) project that aims to provide public software signing and transparency to improve open source supply chain security.
As part of the sigstore project, [Cosign](https://github.com/sigstore/cosign) allows seamless container signing, verification and storage.
You can read more about it [here](https://blog.sigstore.dev/).

Connaisseur currently supports the elementary function of verifying Cosign-generated signatures based on the following types of keys:

- [Locally-generated key pair](https://github.com/sigstore/cosign#generate-a-keypair)
- [KMS](https://github.com/sigstore/cosign#kms-support) (via [reference URI](https://docs.sigstore.dev/key_management/overview/#basic-usage) or [export of the public key](https://github.com/sigstore/cosign#kms-support))
- [Hardware-based token](https://github.com/sigstore/cosign#hardware-based-tokens) ([export the public key](https://github.com/sigstore/cosign/blob/main/USAGE.md#retrieve-the-public-key-from-a-private-key-or-kms))

We plan to expose further features of Cosign and sigstore in upcoming releases, so stay tuned!

## Basic usage

Getting started with Cosign is very well described in the [docs](https://github.com/sigstore/cosign).
You can download Cosign from its [GitHub repository](https://github.com/sigstore/cosign/releases).
In short: After installation, a keypair is generated via:

```bash
cosign generate-key-pair
```

You will be prompted to set a password, after which a private (`cosign.key`) and public (`cosign.pub`) key are created.
You can then use Cosign to sign a container image using:

```bash
# Here, ${IMAGE} is REPOSITORY/IMAGE_NAME:TAG
cosign sign --key cosign.key ${IMAGE}
```

The created signature can be verfied via:

```bash
cosign verify --key cosign.pub ${IMAGE}
```

To use Connaisseur with Cosign, configure a validator in `charts/connaisseur/values.yaml` with the generated public key (`cosign.pub`) as a trust root.
The entry in `.application.validators` should look something like this (make sure to add your own public key to trust root `default`):

```yaml title="charts/connaisseur/values.yaml"
- name: customvalidator
  type: cosign
  trustRoots:
  - name: default
    key: |  # YOUR PUBLIC KEY BELOW
      -----BEGIN PUBLIC KEY-----
      MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEvtc/qpHtx7iUUj+rRHR99a8mnGni
      qiGkmUb9YpWWTS4YwlvwdmMDiGzcsHiDOYz6f88u2hCRF5GUCvyiZAKrsA==
      -----END PUBLIC KEY-----
```

In `.application.policy`, add a pattern to match your public key to your own repository:

```yaml title="charts/connaisseur/values.yaml"
- pattern: "docker.io/securesystemsengineering/testimage:co*"  # YOUR REPOSITORY
  validator: customvalidator
```

After installation, you are ready to verify your images against your public key:

```bash
helm install connaisseur helm --atomic --create-namespace --namespace connaisseur
```

A quick guide for installation and testing is available in [getting started](../getting_started.md#deploy-connaisseur).
In case you just use the default values for the validator and image policy given above, you are able to successfully validate our signed testimage:

```bash
kubectl run signed --image=docker.io/securesystemsengineering/testimage:co-signed
```

And compare this to the unsigned image:

```bash
kubectl run unsigned --image=docker.io/securesystemsengineering/testimage:co-unsigned
```

Or signed with a different key:

```bash
kubectl run altsigned --image=docker.io/securesystemsengineering/testimage:co-signed-alt
```

## Configuration options

`.application.validators[*]` in `charts/connaisseur/values.yaml` supports the following keys for Cosign (refer to [basics](../basics.md#validators) for more information on default keys):

| Key | Default | Required | Description |
| - | - | - | - |
| `name` | - | :heavy_check_mark: | See [basics](../basics.md#validators). |
| `type` | - | :heavy_check_mark: | `cosign`; the validator type must be set to `cosign`. |
| `trustRoots[*].name` | - | :heavy_check_mark: | See [basics](../basics.md#validators). |
| `trustRoots[*].key` | - | :heavy_check_mark: if not using keyless | See [basics](../basics.md#validators). Public key from `cosign.pub` file or [KMS URI](https://docs.sigstore.dev/key_management/overview/#basic-usage). See additional notes [below](#kms-support). |
| `trustRoots[*].keyless.issuer` | - | :heavy_check_mark: if not using a key or issuerRegex | The OIDC provider URL which attests the identity. |
| `trustRoots[*].keyless.subject` | - | :heavy_check_mark: if not using a key or subjectRegex | The identity that created the keyless signature. Usually an email address. |
| `trustRoots[*].keyless.issuerRegex` | - | :heavy_check_mark: if not using a key or issuer | Regex for the OIDC provider URL which attests the identity. |
| `trustRoots[*].keyless.subjectRegex` | - | :heavy_check_mark: if not using a key or subject | Regex of the identity that created the keyless signature. Usually an email address. When setting this, make sure you control all subject that can be matched. The pattern `your.name@gmail.*` also matches `yourXname@gmail.com` or `your.name@gmail.attacker.com` |
| `host.rekor` | `rekor.sigstore.dev` | - | Rekor URL to use for validation against the transparency log (default sigstore instance is `rekor.sigstore.dev`). Setting `host` enforces successful transparency log check to pass verification. See additional notes [below](#transparency-log-verification). |
| `host.rekorPubkey` | Public key of `rekor.sigstore.dev` | - | Public key used to verify signature of log entry from Rekor. |
| `host.fulcioCert` | Root and intermediate certificates belonging to `fulcio.sigstore.dev` | - | The root certificate belonging the Fulcio CA which is used to create keyless signatures. |
| `host.ctLogPubkey` | Public key for the certificate transparency log provided by Sigstore | - | The public key needed for verifying Signed Certificate Timestamps (SCT). This will accept a single key. |
| `auth.` | - | - | Authentication credentials for registries with restricted access (e.g. private registries or ratelimiting). See additional notes [below](#authentication). |
| `auth.secretName` | - | - | Name of a Kubernetes secret in Connaisseur namespace that contains [dockerconfigjson](https://kubernetes.io/docs/concepts/configuration/secret/#docker-config-secrets) for registry authentication. See additional notes [below](#dockerconfigjson). |
| `auth.useKeychain` | `false` | - | When true, pass `--k8s-keychain` argument to `cosign verify` in order to use workload identities for authentication. See additional notes [below](#k8s-keychain). |
| `cert` | - | - | A TLS certificate in PEM format for private registries with self-signed certificates. |

`.application.policy[*]` in `charts/connaisseur/values.yaml` supports the following additional keys and modifications for sigstore/Cosign (refer to [basics](../basics.md#image-policy) for more information on default keys):

| Key | Default | Required | Description |
| - | - | - | - |
| `with.trustRoot` | - | - | Setting the name of trust root to `"*"` enables verification of multiple trust roots. Refer to section on [multi-signature verification](#multi-signature-verification) for more information. |
| `with.threshold` | - | - | Minimum number of signatures required in case `with.trustRoot` is set to `"*"`. Refer to section on [multi-signature verification](#multi-signature-verification) for more information. |
| `with.required` | `[]` | - | Array of required trust roots referenced by name in case `with.trustRoot` is set to `"*"`. Refer to section on [multi-signature verification](#multi-signature-verification) for more information. |
| `with.verifyInTransparencyLog` | `true` | - | Whether to include the verification using the Rekor tranparency log in the verification process. Refer to [Tranparency log verification](#transparency-log-verification) for more information. |
| `with.verifySCT` | `true` | - | Whether to verify the signed certificate timestamps inside the transparency log. |


### Example


??? abstract "charts/connaisseur/values.yaml"
    ```yaml title="charts/connaisseur/values.yaml"
    application:
      validators:
      - name: myvalidator
        type: cosign
        trustRoots:
        - name: mykey
          key: |
            -----BEGIN PUBLIC KEY-----
            MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEvtc/qpHtx7iUUj+rRHR99a8mnGni
            qiGkmUb9YpWWTS4YwlvwdmMDiGzcsHiDOYz6f88u2hCRF5GUCvyiZAKrsA==
            -----END PUBLIC KEY-----

      policy:
      - pattern: "docker.io/securesystemsengineering/testimage:co-*"
        validator: myvalidator
        with:
          key: mykey
    ```


## Additional notes

### Authentication

When using a private registry for images and signature data, the credentials need to be provided to Connaisseur. There are two ways to do this.

#### dockerconfigjson

Create a [dockerconfigjson](https://kubernetes.io/docs/concepts/configuration/secret/#docker-config-secrets) Kubernetes secret in the Connaisseur namespace and pass the secret name to Connaisseur as `auth.secretName`.
The secret can for example be created directly from your local `config.json` (for docker this resides in `~/.docker/config.json`):

```bash
kubectl create secret generic my-secret \
  --from-file=.dockerconfigjson=path/to/config.json \
  --type=kubernetes.io/dockerconfigjson \
  -n connaisseur
```

The secret can also be generated directly from supplied credentials (which may differ from your local `config.json`, using:

```bash
kubectl create secret docker-registry my-secret \
  --docker-server=https://index.docker.io/v1/ \
  --docker-username='<your username>' \
  --docker-password='<your password>' \
  -n connaisseur
```

!!! info
    At present, it [seems to be necessary](https://github.com/sigstore/cosign/issues/587#issuecomment-1062510930) to suffix your registry server URL with `/v1/`.
    This may become unnecessary in the future.

In the above cases, the secret name in Connaisseur configuration would be `secretName: my-secret`.
It is possible to provide one Kubernetes secret with a `config.json` for authentication to multiple private registries and referencing this in multiple validators.

#### K8s keychain

Specification of `auth.useKeychain: true` in the validator configuration passes the `--k8s-keychain` to `cosign` when performing image validation.
Thus, [k8schain](https://pkg.go.dev/github.com/google/go-containerregistry/pkg/authn/k8schain) is used by `cosign` to pick up ambient registry credentials from the environment and for example use workload identities in case of common cloud providers.

For example, when validating against an ECR private repository, the credentials of an IAM user allowed to perform actions
`ecr:GetAuthorizationToken`, `ecr:BatchGetImage`, and `ecr:GetDownloadUrlForLayer` could be added to the secret `connaisseur-env-secrets`:

```yaml
apiVersion: v1
kind: Secret
type: Opaque
metadata:
  name: connaisseur-env-secrets
  ...
data:
  AWS_ACCESS_KEY_ID: ***
  AWS_SECRET_ACCESS_KEY: ***
  ...
```

If `useKeychain` is set to `true` in the validator configuration, `cosign` will log into ECR at time of validation.
See [this cosign pull request](https://github.com/sigstore/cosign/pull/972) for more details.

### KMS Support

Connaisseur supports Cosign's URI-based [KMS integration](https://github.com/sigstore/cosign/blob/main/KMS.md) to manage the signing and verification keys.
Simply configure the trust root key value as the respective URI.
In case of a [Kubernetes secret](https://github.com/sigstore/cosign/blob/main/KMS.md#kubernetes-secret), this would take the following form:

```yaml title="charts/connaisseur/values.yaml"
- name: myvalidator
  type: cosign
  trustRoots:
  - name: mykey
    key: k8s://connaisseur/cosignkeys
```

For that specific case of a Kubernetes secret, make sure to place it in a suitable namespace and grant Connaisseur access to it[^1].

[^1]: The corresponding role and rolebinding should look similar to the following:
```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: connaisseur-kms-role
  namespace: connaisseur  # namespace of respective k8s secret, might have to change that
  labels:
    app.kubernetes.io/name: connaisseur
rules:
- apiGroups: ["*"]
  resources: ["secrets"]
  verbs: ["get"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: connaisseur-kms-rolebinding
  namespace: connaisseur  # namespace of respective k8s secret, might have to change that
  labels:
    app.kubernetes.io/name: connaisseur
subjects:
- kind: ServiceAccount
  name: connaisseur-serviceaccount
  namespace: connaisseur  # Connaisseur's namespace, might have to change that
roleRef:
  kind: Role
  name: connaisseur-kms-role
  apiGroup: rbac.authorization.k8s.io
```
Make sure to adjust it as needed.

Most other KMS will require credentials for authentication that must be provided via environment variables.
Such environment variables can be injected into Connaisseur via `deployment.envs` in `charts/connaisseur/values.yaml`, e.g.:

```yaml title="charts/connaisseur/values.yaml"
  envs:
    VAULT_ADDR: myvault.com
    VAULT_TOKEN: secrettoken
```

### Multi-signature verification

Connaisseur can verify multiple signatures for a single image.
It is possible to configure a threshold number and specific set of required valid signatures.
This allows to implement several advanced use cases (and policies):

* Five maintainers of a repository are able to sign a single derived image, however at least 3 signatures are required for the image to be valid.
* In a CI pipeline, a container image is signed directly after pushing by the build job and at a later time by passing quality gates such as security scanners or integration tests, each with their own key (trust root). Validation requires all of these signatures for deployment to enforce integrity and quality gates.
* A mixture of the above use cases whereby several specific trust roots are enforced (e.g. automation tools) and the overall number of signatures has to surpass a certain threshold (e.g. at least one of the testers admits).
* Key rotation is possible by adding a new key as an additional key and require at least one valid signature.

Multi-signature verification is scoped to the trust roots specified within a referenced validator.
Consider the following validator configuration:

```yaml title="charts/connaisseur/values.yaml"
application:
  validators:
  - name: multicosigner
    type: cosign
    trustRoots:
    - name: alice
      key: |
        -----BEGIN PUBLIC KEY-----
        MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEusIAt6EJ3YrTHdg2qkWVS0KuotWQ
        wHDtyaXlq7Nhj8279+1u/l5pZhXJPW8PnGRRLdO5NbsuM6aT7pOcP100uw==
        -----END PUBLIC KEY-----
    - name: bob
      key: |
        -----BEGIN PUBLIC KEY-----
        MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAE01DasuXJ4rfzAEXsURSnbq4QzJ6o
        EJ2amYV/CBKqEhhl8fDESxsmbdqtBiZkDV2C3znIwV16SsJlRRYO+UrrAQ==
        -----END PUBLIC KEY-----
    - name: charlie
      key: |
        -----BEGIN PUBLIC KEY-----
        MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEEHBUYJVrH+aFYJPuryEkRyE6m0m4
        ANj+o/oW5fLRiEiXp0kbhkpLJR1LSwKYiX5Toxe3ePcuYpcWZn8Vqe3+oA==
        -----END PUBLIC KEY-----
```

The trust roots `alice`, `bob`, and `charlie` are all included for verification in case `.application.policy[*].with.trustRoot` is set to `"*"` (note that this is a special flag, not a real wildcard):

```yaml title="charts/connaisseur/values.yaml"
- pattern: "*:*"
  validator: multicosigner
  with:
    trustRoot: "*"
```

As neither `threshold` nor `required` are specified, Connaisseur will require signatures of all trust roots (`alice`, `bob`, and `charlie`) and deny an image otherwise.
If either `threshold` or `required` is specified, it takes precedence.
For example, it is possible to configure a threshold number of required signatures via the `threshold` key:

```yaml title="charts/connaisseur/values.yaml"
- pattern: "*:*"
  validator: multicosigner
  with:
    trustRoot: "*"
    threshold: 2
```

In this case, valid signatures of two or more out of the three trust roots are required for admittance.
Using the `required` key, it is possible to enforce specific trusted roots:

```yaml title="charts/connaisseur/values.yaml"
- pattern: "*:*"
  validator: multicosigner
  with:
    trustRoot: "*"
    required: ["alice", "bob"]
```

Now, only images with valid signatures of trust roots `alice` and `bob` are admitted.
It is possible to combine `threshold` and `required` keys:

```yaml title="charts/connaisseur/values.yaml"
- pattern: "*:*"
  validator: multicosigner
  with:
    trustRoot: "*"
    threshold: 3
    required: ["alice", "bob"]
```

Thus, at least 3 valid signatures are required and `alice` and `bob` must be among those.


### Transparency log verification

The sigstore project contains a transparency log called [Rekor](https://docs.sigstore.dev/rekor/overview) that provides an immutable, tamper-resistant ledger to record signed metadata to an immutable record.
While it is possible to run your own instance, a public instance of Rekor is available at [rekor.sigstore.dev](https://rekor.sigstore.dev/).
With Connaisseur it is possible to verify that a signature was added to the transparency log via the validators `host.rekor` key (see [Cosign docs](https://github.com/sigstore/cosign/tree/main#rekor-support)).
When the `host.rekor` key is set, e.g. to `rekor.sigstore.dev` for the public instance, Connaisseur requires that a valid signature was added to the transparency log and deny an image otherwise.
Furthermore, the `host.rekor` allows switching to private Rekor instances, e.g. for usage with [keyless signatures](#keyless-signatures).
To disable this feature the `with.verifyInTransparencyLog` key can be set to `false`. This is useful for example if the signature was made without an upload to the transparency log in the first place.


### Keyless signatures

Keyless signatures are a feature of Sigstore that allows to sign container images without the need to manage a private key. Instead the signatures are bound to identities, attested by OIDC providers, and use ephemeral keys, short-lived certificates and a transparency log under the hood to provide similar security guarantees. Further information on this topic can be found [here](https://docs.sigstore.dev/signing/overview/).

When using keyless signatures, the `trustRoots[*].keyless` field can be used to specify the issuer and subject of the keyless signature. The issuer is the OIDC provider that attests the identity and the subject is the identity that created the keyless signature, usually an email address. Both fields are also available as regular expressions. The following example shows how to configure a validator for keyless signatures:

```yaml title="charts/connaisseur/values.yaml"
- name: keylessvalidator
  type: cosign
  trustRoots:
  - name: keyless
    keyless:
      issuerRegex: "github"
      subject: "philipp.belitz@securesystems.de
```

In case the signature was created using the Sigstore infrastructure, nothing else needs to be configured since Connaisseur will automatically retrieve all needed public keys and certificates from the Sigstore infrastructure. If the signature was created using a private infrastructure, the `host.fulcioCert` field can be used to specify the root certificate belonging to the Fulcio CA which is used to create the keyless signatures. The `host.fulcioCert` field should contain the root certificate in PEM format. The same applies to the `host.ctLogPubkey` field which can be used to specify the public key needed for verifying Signed Certificate Timestamps (SCT) and the `host.rekorPubkey` field which can be used to specify the public key used to verify the signature of log entries from Rekor.

```yaml title="charts/connaisseur/values.yaml"
name: default
type: cosign
host:
  rekorPubkey: |
    -----BEGIN PUBLIC KEY-----
    ...
    -----END PUBLIC KEY-----
  ctLogPubkey: |
    -----BEGIN PUBLIC KEY-----
    ...
    -----END PUBLIC KEY-----
  fulcioCert: |
    -----BEGIN CERTIFICATE-----
    ...
    -----END CERTIFICATE-----
  ...
```
