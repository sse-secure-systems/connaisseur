# Notary (V1) / DCT

[Notary](https://github.com/theupdateframework/notary) (V1[^1]) works as an external service holding signatures and trust data of artifacts based on [The Update Framework (TUF)](https://theupdateframework.io/).
[Docker Content Trust (DCT)](https://docs.docker.com/engine/security/trust/) is a client implementation by Docker to manage such trust data for container images like signing images or verifying the corresponding signatures.
It is part of the standard Docker CLI (`docker`) and for example provides the [`docker trust`](https://docs.docker.com/engine/reference/commandline/trust/) commands.

[^1]: Notary does traditionally not carry the version number. However, in differentiation to the new [Notary V2 project](https://github.com/notaryproject/notaryproject) we decided to add a careful "(V1)" whenever we refer to the original project.

Using DCT, the trust data is per default pushed to the Notary server associated to the container registry.
However, not every public container registry provides an associated Notary server and thus support for DCT must be checked for the provider in question.
[Docker Hub](https://hub.docker.com/) for example, runs an associated Notary server (notary.docker.io) and even uses it to serve trust data for the [Docker Official Images](https://docs.docker.com/docker-hub/official_images/).
In fact, since Connaisseur's pre-built images are shared via the [Connaisseur Docker Hub repository](https://hub.docker.com/repository/docker/securesystemsengineering/connaisseur), its own trust data is maintained on Docker Hub's Notary server.
Besides the public Notary instances, Notary can also be run as a private or even standalone instance.
[Harbor](https://goharbor.io/) for example comes along with an associated Notary instance.

Validating a container image via DCT requires a repository's public root key as well as fetching the repository's trust data from the associated Notary server.
While DCT relies on *trust on first use* (TOFU) for repositories' public root keys, Connaisseur enforces manual pinning to a public root key that must be configured in advance.

## Basic usage

In order to validate signatures using Notary, you will either need to create signing keys and signed images yourself or extract the public root key of other images and configure Connaisseur via `validators[*].trust_roots[*].key` in `helm/values.yaml` to pin trust to those keys.
Both is described below.
However, there is also step-by-step instructions for using Notary in the [getting started guide](../getting_started.md).

### Creating signing key pairs

You can either create the root key manually or push an image with DCT enabled upon which `docker` will guide you to set up the keys as described in the next section.
In order to generate a public-private root key pair manually, you can use:

```bash
docker trust key generate root
```

You will be prompted for a password, the private key is automatically imported and a `root.pub` file is created in your current folder that contains your public key which should look similar to:

```bash
-----BEGIN PUBLIC KEY-----
role: root

MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAELDzXwqie/P66R3gVpFDWMhxOyol5
YWD/KWnAaEIcJVTYUR+21NJSZz0yL7KLGrv50H9kHai5WWVsVykOZNoZYQ==
-----END PUBLIC KEY-----
```

You will only need the actual base64 encoded part for configuring the `validators[*].trust_roots[*].key` in `helm/values.yaml` of Connaisseur to validate your images.
How to extract the public root key for any image is described [below](#getting-the-public-root-key).

### Creating signatures

Before you can start validating images using the Notary (V1) validator, you'll first need an image which has been signed using DCT.
Easiest way to do this is by pushing an image of your choice (e.g. `busybox:stable`) to your Docker Hub repository with DCT activated (either set the environment variable `DOCKER_CONTENT_TRUST=1` or use the `--disable-content-trust=false` flag).
If you haven't created any signatures for images in the current repository yet, you'll be asked to enter a passphrase for a root key and targets key, which get generated on your machine.
Have a look into the [TUF documentation](https://theupdateframework.github.io/specification/latest/#roles-and-pki) to read more about TUF roles and their meanings.
If you already have these keys, just enter the required passphrase.

```bash
DOCKER_CONTENT_TRUST=1 docker push <your-repo>/busybox:stable
> The push refers to repository [<your-repo>/busybox]
> 5b8c72934dfc: Pushed
> stable: digest: sha256:dca71257cd2e72840a21f0323234bb2e33fea6d949fa0f21c5102146f583486b size: 527
> Signing and pushing trust metadata
> You are about to create a new root signing key passphrase. This passphrase
> will be used to protect the most sensitive key in your signing system. Please
> choose a long, complex passphrase and be careful to keep the password and the
> key file itself secure and backed up. It is highly recommended that you use a
> password manager to generate the passphrase and keep it safe. There will be no
> way to recover this key. You can find the key in your config directory.
> Enter passphrase for new root key with ID 5fb3e1e:
> Repeat passphrase for new root key with ID 5fb3e1e:
> Enter passphrase for new repository key with ID 6c2a04c:
> Repeat passphrase for new repository key with ID 6c2a04c:
> Finished initializing "<your-repo>/busybox"
```

The freshly generated keys are directly imported to the Docker client.
Private keys reside in `~/.docker/trust/private` and public trust data is added to `~/.docker/trust/tuf/`.
The created signature for your image is pushed to the public Docker Hub Notary (notary.docker.io).
The private keys and password are required whenever a new version of the image is pushed with DCT activated.

### Getting the public root key

Signature validation via Connaisseur requires the [public root key](https://theupdateframework.github.io/specification/latest/#root) to verify against as a trust anchor.
But from where do you get this, especially for public images whose signatures you didn't create?
We have created the *get_root_key* utility to extract the public root key of images.
To use it, either use our pre-built image or build the docker image yourself via `docker build -t get-public-root-key -f docker/Dockerfile.getRoot .` and run it on the image to be verified:

```bash
# pre-built
docker run --rm docker.io/securesystemsengineering/get-public-root-key -i securesystemsengineering/testimage
# or self-built
docker run --rm get-public-root-key -i securesystemsengineering/testimage
> KeyID: 76d211ff8d2317d78ee597dbc43888599d691dbfd073b8226512f0e9848f2508
> Key: -----BEGIN PUBLIC KEY-----
> MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEsx28WV7BsQfnHF1kZmpdCTTLJaWe
> d0CA+JOi8H4REuBaWSZ5zPDe468WuOJ6f71E7WFg3CVEVYHuoZt2UYbN/Q==
> -----END PUBLIC KEY-----
```

The `-i` (`--image`) option is required and takes the image, for which you want the public key.
There is also the `-s` (`--server`) option, which defines the Notary server that should be used and which defaults to `notary.docker.io`.

The public repository root key resides with the signature data in the Notary instance, so what the *get_root_key* utility does in the background is just fetching, locating and parsing the public repository root key for the given image.

### Configuring and running Connaisseur

Now that you either created your own keys and signed images or extracted the public key of other images, you will need to configure Connaisseur to use those keys for validation.
This is done via `validators` in `helm/values.yaml`.
The corresponding entry should look similar to the following (using the extracted public key as trust root):

```yaml
- name: customvalidator
  type: notaryv1
  host: notary.docker.io
  trust_roots:
  - name: default
    key: |  # THE DESIRED PUBLIC KEY BELOW
      -----BEGIN PUBLIC KEY-----
      MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEOXYta5TgdCwXTCnLU09W5T4M4r9f
      QQrqJuADP6U7g5r9ICgPSmZuRHP/1AYUfOQW3baveKsT969EfELKj1lfCA==
      -----END PUBLIC KEY-----
```

You also need to create a corresponding entry in the image policy via `policy` in `helm/values.yaml`, for example:

```yaml
- pattern: "docker.io/<REPOSITORY>/<IMAGE>:*"  # THE DESIRED REPOSITORY
  validator: customvalidator
```

After installation, you are ready to verify your images against your public key:

```bash
helm install connaisseur helm --atomic --create-namespace --namespace connaisseur
```

Connaisseur now rejects all images from the given repository that have not been signed based on the provided public key.
A quick guide for installation and testing is available in [getting started](../getting_started.md#deploy-connaisseur).
It also provides a full step-by-step guide.

### Understanding validation

Using the simple pre-configuration shipped with Connaisseur, it is possible to test validation by deploying some pods:

```bash
kubectl run test-signed --image=docker.io/securesystemsengineering/testimage:signed
> pod/test-signed created

kubectl run test-unsigned --image=docker.io/securesystemsengineering/testimage:unsigned
> Error from server: admission webhook "connaisseur-svc.connaisseur.svc" denied the request: Unable to find signed digest for image docker.io/securesystemsengineering/testimage:unsigned.
# or in case of a signature with a different key
> Error from server: admission webhook "connaisseur-svc.connaisseur.svc" denied the request: Failed to verify signature of trust data root.
```

How does Connaisseur validate these requests and convert the images with tags to digests?
What happens in the background is that Connaisseur looks up trust data of the image in the `root`, `snapshot`, `timestamp` and `targets` files (in json format) by querying the API of the Notary server.
Trust data syntax is validated against their known schemas and the files' signatures are validated against their respective public keys.
The pinned root key is used for the `root.json` file that in turn contains the other keys which can then be trusted for validation of the remaining trust data (`snapshot.json`, `timestamp.json`, `targets.json`).
Furthermore, Connaisseur gathers trust data of potential delegations linked in the `targets` file which can then be used to [enforce delegations](#enforcing-delegations).

At this point, Connaisseur is left with a validated set of trust data.
Connaisseur filters the trust data for consistent signed digests that actually relate to the image under validation.
In case exactly one trusted digest remains, Connaisseur modifies the admission request and admits it.
Otherwise, admission is rejected.

While it is obvious to reject an image that does not exhibit a trusted digest, there is the special case of multiple trusted digests.
This only occurs in some edge cases, but at this point Connaisseur cannot identify the right digest anymore and consequently has to reject.

For more information on TUF roles, please refer to [TUF's documentation](https://theupdateframework.io/security/) or checkout [this introductory presentation](https://berlin-crypto.github.io/event/dockerimagesignatures.html) on how the trust data formats work and are validated by Connaisseur.

## Configuration options

`.validators[*]` in `helm/values.yaml` supports the following keys for Notary (V1) (refer to [basics](../basics.md#validators) for more information on default keys):

| Key | Default | Required | Description |
| - | - | - | - |
| `name` | - | :heavy_check_mark: | See [basics](../basics.md#validators). |
| `type` | - | :heavy_check_mark: | `notaryv1`; the validator type must be set to `notaryv1`. |
| `host` | - | :heavy_check_mark: | URL of the Notary instance, in which the signatures reside, e.g. `notary.docker.io`. |
| `trust_roots[*].name` | - | :heavy_check_mark: | See [basics](../basics.md#validators). |
| `trust_roots[*].key` | - | :heavy_check_mark: | See [basics](../basics.md#validators). ECDSA public root key. |
| `auth` | - | | Authentication credentials for the Notary server in case the trust data is not public. |
| `auth.secret_name` | - | | (Preferred over `username` + `password` combination.) Name of a Kubernetes secret that must exist beforehand. Create a file `auth.yaml` containing <br/>&nbsp;&nbsp; `username: <user>` <br/>&nbsp;&nbsp; `password: <password>` <br/> and run `kubectl create secret generic <kube-secret-name> --from-file auth.yaml`.|
| `auth.username` | - | | Username to authenticate with. It is recommended to use `auth.secret_name` instead. |
| `auth.password` | - | | Password or access token to authenticate with. It is recommended to use `auth.secret_name` instead. |
| `cert` | - | | Self-signed certificate of the Notary instance, if used. Certificate must be supplied in `.pem` format. |
| `is_acr` | `false` | | `true` if using Azure Container Registry (ACR) as ACR does not offer a health endpoint according to Notary API specs. |

`.policy[*]` in `helm/values.yaml` supports the following additional keys for Notary (V1) (refer to [basics](../basics.md#image-policy) for more information on default keys):

| Key | Default | Required | Description |
| - | - | - | - |
| `with.delegations` | - | | List of delegation names to enforce specific signers to be present. Refer to section on [enforcing delegations](#enforcing-delegations) for more information. |

#### Example

```yaml
validators:
- name: docker_essentials
  type: notaryv1
  host: notary.docker.io
  trust_roots:
  - name: sse
    key: |
      -----BEGIN PUBLIC KEY-----
      MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEvtc/qpHtx7iUUj+rRHR99a8mnGni
      qiGkmUb9YpWWTS4YwlvwdmMDiGzcsHiDOYz6f88u2hCRF5GUCvyiZAKrsA==
      -----END PUBLIC KEY-----

policy:
- pattern: "docker.io/securesystemsengineering/connaisseur:*"
  validator: docker_essentials
  with:
    key: sse
    delegations:
    - belitzphilipp
    - starkteetje
```

## Additional notes

### Enforcing delegations

Notary (V1) offers the functionality to delegate trust.
To better understand this feature, it's best to have a basic understanding of the TUF key hierarchy, or more specifically the purpose of the root, targets and delegation keys.
If you are more interested in this topic, please read the [TUF documentation](https://theupdateframework.github.io/specification/latest/#roles-and-pki).

When creating the signatures of your docker images earlier, two keys were generated -- the root key and the targets key.
The root key is the root of all trust and will be used whenever a new image repository is created and needs to be signed.
It's also used to rotate all other kinds of keys, thus there is usually only one root key present.
The targets key is needed for new signatures on one specific image repository, hence every image repository has its own targets key.
Hierarchically speaking, the targets keys are below the root key, as the root key can be used to rotate the targets keys should they get compromised.

Delegations will now go one level deeper, meaning they can be used to sign individual image repositories and only need the targets key for rotation purposes, instead of the root key.
Also delegation keys are not bound to individual image repositories, so they can be re-used multiple times over different image repositories.
So in a sense they can be understood as keys for individual signers.

To create a delegation key run:

```bash
docker trust key generate <key-name>
> Generating key for <key-name>...
> Enter passphrase for new <key-name> key with ID 9deed25:
> Repeat passphrase for new <key-name> key with ID 9deed25:
> Successfully generated and loaded private key. Corresponding public key available: <current-directory>/<key-name>.pub
```

This delegation key now needs to be added as a signer to a respective image repository, like the `busybox` example [above](#creating-signatures).
In doing so, you'll be asked for the targets key.

```bash
docker trust signer add --key <key-name>.pub <key-name> <your-repo>/busybox
> Adding signer "<key-name>" to <your-repo>/busybox...
> Enter passphrase for repository key with ID b0014f8:
> Successfully added signer: <key-name> to <your-repo>/busybox
```

If you create a new signature for the image, you'll be asked for your delegation key instead of the targets key, therefore creating a signature using the delegation.

```bash
> DOCKER_CONTENT_TRUST=1 docker push <your-repo>/busybox:stable
```

Without further configuration, Connaisseur will accept all delegation signatures for an image that can ultimately be validated against the public root key.
Connaisseur can enforce a certain signer/delegation (or multiple) for an image's signature via the `with.delegations` list inside an image policy rule.
Simply add the signer's name to the list.
You can also add multiple signer names to the list in which case Connaisseur will enforce that *all* delegations must have signed a matching image.

```yaml
policy:
- pattern: "<your-repo>/busybox:*"
  with:
    delegations:
    - <key-name>
    - <other-key-name>
```

The delegation feature can be useful in complex organisations where certain people may be required to sign specific critical images.
Another use case is to sign an image with delegation keys in various stages of your CI and enforce that certain checks were passed, i.e. enforcing the signature of your linter, your security scanner and your software lisence compliance check.

### Using Azure Container Registry

Using Azure Container Registry (ACR) must be specified in the [validator configuration](./notaryv1.md#configuration-options) by setting `is_acr` to `true`.

Moreover, you need to provide credentials of an Azure Identity having at least `read` access to the ACR (and, thus, to the associated Notary instance). Assuming you have the `az cli` installed you can create a Service Principal for this by running:

```bash
# Retrieve the ID of your registry
REGISTRY_ID=$(az acr show --name <ACR-NAME>  --query 'id' -otsv)

# Create a service principal with the Reader role on your registry
az ad sp create-for-rbac --name "<SERVICE-PRINCIPLE-NAME>" --role Reader --scopes ${REGISTRY_ID}
```

Use the resulting `applicationID` as `auth.username`, the resulting `password` as `auth.password` and set `<ACR>.azurecr.io` as `host` in the `helm/values.yaml` and you're ready to go!

