# Getting Started

This guide offers a simple default configuration for setting up Connaisseur using public infrastructure and verifying your first self-signed images.
You will learn how to:

1. [Create signing key pairs](#create-signing-key-pairs)
2. [Configure Connaisseur](#configure-connaisseur)
3. [Deploy Connaisseur](#deploy-connaisseur)
4. [Test Connaisseur](#test-connaisseur) *(and sign images)*
5. [Cleanup](#cleanup)

In the tutorial, you can choose to use either Notary (V1) via Docker Content Trust (DCT) or Cosign from the sigstore project as a signing solution referred to as DCT and Cosign from here on.
Furthermore we will work with public images on [Docker Hub](https://hub.docker.com/) as a container registry and a Kubernetes test cluster which might for example be [MicroK8s](https://microk8s.io/) or [minikube](https://minikube.sigs.k8s.io/docs/) for local setups.
However, feel free to bring your own solutions for registry or cluster and check out our notes on [compatibility](./README.md#compatibility).

In general, Connaisseur can be fully configured via `helm/values.yaml`, so feel free to take a look and try for yourself.
For more advanced usage in more complex cases (e.g. authentication, multiple registries, signers, validators, additional features), we strongly advise to review the following pages:

- [Basics](./basics.md): *understanding, configuring and using Connaisseur (e.g. image policy and validators)*
- [Validators](./validators/README.md): *applying different signature solutions and specific configurations*
- [Features](./features/README.md): *using additional features (e.g. alerting)*

In case you need help, feel free to reach out via [GitHub Discussions](https://github.com/sse-secure-systems/connaisseur/discussions) :wave:

> :octicons-light-bulb-16: **Note**: As more than only public keys can be used to validate integrity and provenance of an image, we refer to these trust anchors in a generalized form as *trust roots*.

## Requirements

You should have a Kubernetes test cluster running.
Furthermore, `docker`, `git`, `helm` and `kubectl` should be installed and usable, i.e. having run `docker login` and switched to the appropriate `kubectl` context.

## Create signing key pairs

Before getting started with Connaisseur, we need to create our signing key pair.
This obviously depends on the signing solution.
Here, we will walk you through it for DCT and Cosign.
In case you have previously worked with Docker Content Trust or Cosign before and already possess key pairs, you can skip this step (how to retrieve a previously created DCT key is described [here](./validators/notaryv1.md#getting-the-public-root-key)).
Otherwise, pick your preferred signing solution below.

In case you are uncertain which solution to go with, you might be better off to start with DCT, as it comes packaged with `docker`.
Cosign on the other hand is somewhat more straightforward to use.

=== "Docker Content Trust"

    General usage of DCT is described in the [docker documentation](https://docs.docker.com/engine/security/trust/).
    Detailed information on all configuration options for Connaisseur is provided in the [Notary (V1) validator section](validators/notaryv1.md).
    For now, we just need to generate a public-private root key pair via:

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

    We will only need the actual base64 encoded part of the key later.

=== "Cosign"

    Usage of Cosign is very well described in the [docs](https://github.com/sigstore/cosign).
    You can download Cosign from its [GitHub repository](https://github.com/sigstore/cosign/releases).
    Detailed information on all configuration options for Connaisseur is provided in the [Cosign validator section](validators/sigstore_cosign.md).
    For now, we just need to generate a key pair via:

    ```bash
    cosign generate-key-pair
    ```

    You will be prompted to set a password, after which a private (`cosign.key`) and public (`cosign.pub`) key are created.
    In the next step, we will need the public key that should look similar to:

    ```bash
    -----BEGIN PUBLIC KEY-----
    MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEvtc/qpHtx7iUUj+rRHR99a8mnGni
    qiGkmUb9YpWWTS4YwlvwdmMDiGzcsHiDOYz6f88u2hCRF5GUCvyiZAKrsA==
    -----END PUBLIC KEY-----
    ```

## Configure Connaisseur

Now, we will need to configure Connaisseur.
Let's first clone the repository:

```bash
git clone https://github.com/sse-secure-systems/connaisseur.git
cd connaisseur
```

Connaisseur is configured via `helm/values.yaml`, so we will start there.
We need to set Connaisseur to use our previously created public key for validation.
To do so, go to the `.validators` and find the `default` validator.
We need to uncomment the trust root with name `default` and add our previously created public key.
The result should look similar to this:

=== "Docker Content Trust"

    ```yaml
    # the `default` validator is used if no validator is specified in image policy
    - name: default
      type: notaryv1  # or other supported validator (e.g. "cosign")
      host: notary.docker.io # configure the notary server to be used
      trust_roots:
      # the `default` key is used if no key is specified in image policy
      - name: default
        key: |  # enter your key below
          -----BEGIN PUBLIC KEY-----
          MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAELDzXwqie/P66R3gVpFDWMhxOyol5
          YWD/KWnAaEIcJVTYUR+21NJSZz0yL7KLGrv50H9kHai5WWVsVykOZNoZYQ==
          -----END PUBLIC KEY-----
      #cert: |  # in case the trust data host is using a self-signed certificate
      #  -----BEGIN CERTIFICATE-----
      #  ...
      #  -----END CERTIFICATE-----
      #auth:  # credentials in case the trust data requires authentication
      #  # either (preferred solution)
      #  secret_name: mysecret  # reference a k8s secret in the form required by the validator type (check the docs)
      #  # or (only for notaryv1 validator)
      #  username: myuser
      #  password: mypass
    ```

=== "Cosign"

    _In addition for Cosign, the `type` needs to be set to `cosign` and the `host` is not required._

    ```yaml
    # the `default` validator is used if no validator is specified in image policy
    - name: default
      type: cosign  # or other supported validator (e.g. "cosign")
      trust_roots:
      # the `default` key is used if no key is specified in image policy
      - name: default
        key: |  # enter your key below
          -----BEGIN PUBLIC KEY-----
          MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEvtc/qpHtx7iUUj+rRHR99a8mnGni
          qiGkmUb9YpWWTS4YwlvwdmMDiGzcsHiDOYz6f88u2hCRF5GUCvyiZAKrsA==
          -----END PUBLIC KEY-----
      #cert: |  # in case the trust data host is using a self-signed certificate
      #  -----BEGIN CERTIFICATE-----
      #  ...
      #  -----END CERTIFICATE-----
      #auth:  # credentials in case the trust data requires authentication
      #  # either (preferred solution)
      #  secret_name: mysecret  # reference a k8s secret in the form required by the validator type (check the docs)
      #  # or (only for notaryv1 validator)
      #  username: myuser
      #  password: mypass
    ```

We have now configured the validator `default` with trust root `default`.
This will automatically be used if no validator and trust root is specified in the image policy (`.policy`).
Per default, Connaisseur's image policy under `.policy` in `helm/values.yaml` comes with a pattern `"*:*"` that does not specify a validator or trust root and thus all images that do not meet any of the more specific pre-configured patterns will be verified using this validator.
Consequently, we leave the rest untouched in this tutorial, but strongly recommend to read the [basics](./basics.md) to leverage the full potential of Connaisseur.

## Deploy Connaisseur

So let's deploy Connaisseur to the cluster:

```bash
helm install connaisseur helm --atomic --create-namespace --namespace connaisseur
```

This can take a few minutes.
You should be prompted something like:

```bash
NAME: connaisseur
LAST DEPLOYED: Fri Jul  9 20:43:10 2021
NAMESPACE: connaisseur
STATUS: deployed
REVISION: 1
TEST SUITE: None
```

Afterwards, we can check that Connaisseur is running via `kubectl get all -n connaisseur` which should look similar to:

```bash
NAME                                          READY   STATUS    RESTARTS   AGE
pod/connaisseur-deployment-6876c87c8c-txrkj   1/1     Running   0          2m9s
pod/connaisseur-deployment-6876c87c8c-wvr7q   1/1     Running   0          2m9s
pod/connaisseur-deployment-6876c87c8c-rnc7k   1/1     Running   0          2m9s

NAME                      TYPE        CLUSTER-IP       EXTERNAL-IP   PORT(S)   AGE
service/connaisseur-svc   ClusterIP   10.152.183.166   <none>        443/TCP   2m10s

NAME                                     READY   UP-TO-DATE   AVAILABLE   AGE
deployment.apps/connaisseur-deployment   3/3     3            3           2m9s

NAME                                                DESIRED   CURRENT   READY   AGE
replicaset.apps/connaisseur-deployment-6876c87c8c   3         3         3       2m9s
```

## Test Connaisseur

Now that we created our key pairs, configured and deployed Connaisseur, the next step is to test our setup.
So let's create and push a test image.
Feel free to use our simple test Dockerfile under `tests/Dockerfile` (make sure to set your own `IMAGE` name):

```bash
# Typically, IMAGE=<REGISTRY>/<REPOSITORY-NAME>/<IMAGE-NAME>:<TAG>, like
IMAGE=docker.io/securesystemsengineering/demo:test
docker build -f tests/Dockerfile -t ${IMAGE} .
docker push ${IMAGE}
```

> In case you have DCT turned on per default via environment variable `DOCKER_CONTENT_TRUST=1`, you should disable for now during the `docker push` by adding the `--disable-content-trust=true`.

If we try to deploy this unsigned image:

```bash
kubectl run test --image=${IMAGE}
```

Connaisseur denies the request due to lack of trust data or signed digest, e.g.:

```bash
Error from server: admission webhook "connaisseur-svc.connaisseur.svc" denied the request: Unable to get root trust data from default.
# or
Error from server: admission webhook "connaisseur-svc.connaisseur.svc" denied the request: No trust data for image "docker.io/securesystemsengineering/demo:test".
# or
Error from server: admission webhook "connaisseur-svc.connaisseur.svc" denied the request: could not find signed digest for image "docker.io/securesystemsengineering/demo:test" in trust data.
```

So let's sign the image and try again.

=== "Docker Content Trust"

    In DCT signing works via `docker push` using the `--disable-content-trust` flag:

    ```bash
    docker push ${IMAGE} --disable-content-trust=false
    ```

    You will be prompted to provide your password and might be asked to set a new repository key.
    The trust data will then be pushed to the Docker Hub Notary server.

=== "Cosign"

    For Cosign, we use the private key file from the first step:

    ```bash
    cosign sign -key cosign.key ${IMAGE}
    ```

    You will be asked to enter your password after wich the signature data will be pushed to your repository.

After successful signing, we try again:

```bash
kubectl run test --image=${IMAGE}
```

Now, the request is admitted to the cluster and Kubernetes returns:

```bash
pod/test created
```

You did it :partying_face: you just verified your first signed images in your Kuberenetes cluster :people_with_bunny_ears_partying:

Read on to learn how to fully configure Connaisseur :tools:


## Cleanup

To uninstall Connaisseur, use:

```bash
helm uninstall connaisseur --namespace connaisseur
```

Uninstallation can take a moment as Connaisseur needs to validate the deletion webhook.

