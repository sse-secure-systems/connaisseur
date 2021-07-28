# sigstore / Cosign

[sigstore](https://sigstore.dev/) is a [Linux Foundation](https://linuxfoundation.org/) project that aims to provide public software signing and transparency to improve open source supply chain security.
As part of the sigstore project, [Cosign](https://github.com/sigstore/cosign) allows seamless container signing, verification and storage.
You can read more about it [here](https://blog.sigstore.dev/).

Connaisseur currently supports the elementary function of verifying Cosign-generated signatures against the locally created corresponding public keys.
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
cosign sign -key cosign.key ${IMAGE}
```

The created signature can be verfied via:

```bash
cosign verify -key cosign.pub ${IMAGE}
```

To use Connaisseur with Cosign, configure a validator in `helm/values.yaml` with the generated public key (`cosign.pub`) as a trust root.
The entry in `.validators` should look something like this (make sure to add your own public key to trust root `default`):

```yaml
- name: customvalidator
  type: cosign
  trust_roots:
  - name: default
    key: |  # YOUR PUBLIC KEY BELOW
      -----BEGIN PUBLIC KEY-----
      MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEvtc/qpHtx7iUUj+rRHR99a8mnGni
      qiGkmUb9YpWWTS4YwlvwdmMDiGzcsHiDOYz6f88u2hCRF5GUCvyiZAKrsA==
      -----END PUBLIC KEY-----
```

In `.policy`, add a pattern to match your public key to your own repository:

```yaml
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

`.validators[*]` in `helm/values.yaml` supports the following keys for Cosign (refer to [basics](../basics.md#validators) for more information on default keys):

| Key | Default | Required | Description |
| - | - | - | - |
| `name` | | :heavy_check_mark: | See [basics](../basics.md#validators). |
| `type` | | :heavy_check_mark: | `cosign`; the validator type must be set to `cosign`. |
| `trust_roots[*].name` | | :heavy_check_mark: | See [basics](../basics.md#validators). |
| `trust_roots[*].key` | | :heavy_check_mark: | See [basics](../basics.md#validators). ECDSA public key from `cosign.pub` file. |
| `host` | | | Not yet implemented. |
| `auth.` | | | Authentication credentials for private registries. |
| `auth.secret_name` | | | Name of a Kubernetes secret that contains [dockerconfigjson](https://kubernetes.io/docs/concepts/configuration/secret/#docker-config-secrets) for registry authentication. See additional notes [below](#authentication). |

### Example

```yaml
validators:
- name: myvalidator
  type: cosign
  trust_roots:
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

When using a private registry for images and signature data, the credentials need to be provided to Connaisseur.
This is done by creating a [dockerconfigjson](https://kubernetes.io/docs/concepts/configuration/secret/#docker-config-secrets) Kubernetes secret and passing the secret name to Connaisseur as `auth.secret_name`.
The secret can for example be created directly from your local `config.json` (for docker this resides in `~/.docker/config.json`):

```bash
kubectl create secret generic my-secret \
  --from-file=.dockerconfigjson=path/to/config.json \
  --type=kubernetes.io/dockerconfigjson -n connaisseur
```

In the above case, the secret name in Connaisseur configuration would be `secret_name: my-secret`.
It is possible to provide one Kubernetes secret with a `config.json` for authentication to multiple private registries and referencing this in multiple validators.

### Verification against transparency log

Connaisseur already verifies signatures against the transparency log.
However, optional enforcement of transparency log is only planned in upcoming releases.

### Keyless signatures

Keyless signatures have not yet been implemented but are planned in upcoming releases.
