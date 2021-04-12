# Setup

Setting up Connaisseur for the first time can be a bit of a hassle, especially if you are not familiar with Docker Content Trust (DCT). Furthermore, Connaisseur requires/links several other services (Kubernetes cluster, container registry, notary server) for which many common providers exist. Hence, we've created multiple guides for various environments to help you on the way. If you still can't get it to work or have any feedback, feel free to reach out to us via [GitHub Discussions](https://github.com/sse-secure-systems/connaisseur/discussions)!

The guide below offers a simple default configuration for setting up Connaisseur using public infrastructure and is aimed at quick testing. It uses [Docker Hub](https://hub.docker.com/) as both container registry and notary, but is expected to work for other solutions as well. It has been tested for the following Kubernetes services:
- [x] [K3s](https://github.com/rancher/k3s)
- [x] [kind](https://kind.sigs.k8s.io/)
- [x] [MicroK8s](https://github.com/ubuntu/microk8s)
- [x] [minikube](https://github.com/kubernetes/minikube)
- [x] [Amazon Elastic Kubernetes Service (EKS)](https://docs.aws.amazon.com/eks/)
- [x] [Azure Kubernetes Service (AKS)](https://docs.microsoft.com/en-us/azure/aks/)
- [x] [Google Kubernetes Engine](https://cloud.google.com/kubernetes-engine/docs/)
- [x] [SysEleven MetaKube](https://docs.syseleven.de/metakube)

Two further specialized guides exist:

1. **Local setup ([minikube](https://github.com/kubernetes/minikube) & [Harbor](https://github.com/goharbor/harbor))**: Connaisseur can be run completely locally with a minikube instance paired with a local Harbor installation that combines registry and notary servers. This setup is a bit more cumbersome since it does not use existing public infrastructure such as PKI. However, it is entirely based on open-source solutions, does not require continuous access to the internet and you control every part of the installation. This makes it specifically suited e.g. for security researchers and users interested in the inner workings of DCT and Connaisseur. Head over to [the respective README](local/README.md) to try it out.

2. **[Azure Kubernetes Services](https://docs.microsoft.com/en-us/azure/aks/) with [Azure Container Registry (ACR)](https://docs.microsoft.com/en-us/azure/container-registry/)**: Microsoft Azure is currently the only one of the big cloud providers with a managed Kubernetes and container registry that supports DCT. If you want to set up Connaisseur with ACR, head over to [the specialized setup guide](acr/README.md).


## Requirements

We assume you have a running Kubernetes cluster already. Since this tutorial works with the CLI, we furthermore assume you have the `docker`, `git`, `helm`, `kubectl`, `make`, `openssl` and `yq` (>= v4) binaries installed and usable, i.e. having run `docker login` and having switched to the appropriate `kubectl` context.

> **MicroK8s**: DNS addon must be activated using `sudo microk8s enable dns`.

> This tutorial was tested on a machine running Ubuntu 20.04.

## Configuration and installation of Connaisseur

### 1. Set up environment

Let's get started by cloning this repository:

```bash
git clone https://github.com/sse-secure-systems/connaisseur.git
cd connaisseur
```

> The default of what you will install when following this guide will always be the latest release of Connaisseur. If you want to run Connaisseur with the most recent changes that haven't yet made it into a release, you will have to [build an image yourself](../CONTRIBUTING.md#setup-the-environment) with `make docker`.

### 2. Set up Docker Content Trust

If you already have a root key configured on your system, you can skip this step (you can check whether there is already a root key file with `grep -iRl "role: root$" ~/.docker/trust/`).

Otherwise, generate a public-private root key pair with `docker trust key generate root`.

>  If you want to stick to only signed images, you can either run `export DOCKER_CONTENT_TRUST=1` or add it to your `.bashrc` (or equivalent) to (permanently) configure `docker` to _only ever_ use signed images. If you do so, you can selectively disable DCT by prefixing a single command by `DOCKER_CONTENT_TRUST=0`.

### 3. Configure Connaisseur

Before you can finally set up Connaisseur, you will need to configure its connection to the notary server provided by Docker Hub (or your notary server of choice) and specify the public key used as trust anchor. These — like all configurations — are done in the `helm/values.yaml`. It is _the_ config file for Connaisseur. If you have some time to spare, have a look :)

> For example, you can turn on detection mode by setting `detection_mode: true`, which will allow your deployments to pass, but will log the violation. This might be useful when rolling out Connaisseur to an existing Kubernetes installation in order to first get a grasp on remaining obstacles before turning on (the default) blocking mode.

#### Configure Notary

In `helm/values.yaml`, we first need to specify the location of our notary under `notary.host`:

```yaml
notary:
  # domain to the notary server. can be `null` or non-existant to use
  # the public Docker Hub notary server
  host: notary.docker.io
```

If you use a public Docker Hub repository, you can keep `notary.auth.enabled` at `false`, skip the following and directly go to the next step [configuring your public key](#set-your-public-key-as-trust-anchor). In case you use a notary server that requires authorization or decide to use a private repository on Docker Hub, you need to pass your credentials to Connaisseur. For simplicity in a test environment, you can just set `notary.auth.enabled` to `true`, `notary.auth.user` to your username or Docker Hub ID and `notary.auth.password` to your password:

```yaml
  # if notary uses an authentication server, give a user and password
  # with pull rights
  auth:
    enabled: true
    # enter user/pass directly
    # these are placeholders and should be changed!
    user: notaryuser
    password: Password123
    # or use a predefined secret, which needs the fields 'NOTARY_USER'
    # and 'NOTARY_PASS'
    secretName: null
```

For security in a real environment, you should first setup and then reference a [Kubernetes secret](https://kubernetes.io/docs/concepts/configuration/secret/) via `secretName`.

> At this point, Connaisseur only supports BasicAuth for connecting to the notary.

#### Set your public key as trust anchor

> What is being done at this point is to set your personal root key as Connaisseur's trust anchor. If used in production, you may wish to go for [setting up delegation keys](https://docs-stage.docker.com/engine/security/trust/trust_delegation/#creating-delegation-keys) and keep the root key away from everyday-signing.

Lastly, we need to configure the `notary.rootPubKey` that serves as a trust anchor and pins all signatures of deployed images to this public key. There is two different ways to get the required key:

1. In case you just setup DCT and created your root keys, you should have a `root.pub` file in your folder. Remove the `role` and empty line and copy the contents to `notary.rootPubKey` in `helm/values.yaml`. The result should look similar to this (except for the different key value):

```yaml
  # the public part of the root key, for verifying notary's signatures
  rootPubKey: |
    -----BEGIN PUBLIC KEY-----
    MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEsx28WV7BsQfnHF1kZmpdCTTLJaWe
    d0CA+JOi8H4REuBaWSZ5zPDe468WuOJ6f71E7WFg3CVEVYHuoZt2UYbN/Q==
    -----END PUBLIC KEY-----
```

2. In case you already had DCT setup or cannot find the file, we need to retrieve and convert the key manually from your previously created root key. For most shell users, there is a short script below. Otherwise, just follow the manual steps:

##### manual

- Go to your private docker trust folder `~/.docker/trust/private` and identify the root key. To do so, you can either go through the files and search for the one with `role: root` or `grep -r 'role: root'`.
- Copy this file to a new file `root-priv.key` and remove line with `role: root` and the following empty line.
- Generate the corresponding public key via `openssl ec -in root-priv.key -pubout -out root.pub`. You will be asked to enter your root password.
- The new `root.pub` contains your public which you copy and set for `notary.rootPubKey` in `connaisseur/helm/values.yaml`. The result should look similar as for the first case above.
- To clean up, remove the `root-priv.key` and `root.pub` in `~/.docker/trust/private`.

##### bash/sh/zsh

- Run the script below from the Connaisseur repository to generate your root public key. You will be asked to enter your root password set above:

```bash
cd ~/.docker/trust/private
sed '/^role:\sroot$/d' $(grep -iRl "role: root$" .) > root-priv.key
openssl ec -in root-priv.key -pubout -out root.pub
```

- After entering your password, copy the public key to the `helm/values.yaml`: 

```bash
yq e '.notary.rootPubKey=$(cat root.pub)' -i "${OLDPWD}/helm/values.yaml"
rm root-priv.key root.pub
cd -
```

- The resulting `/helm/values.yaml` should have an excerpt looking similar to what is shown in the first case above.

### 4. Deploy Connaisseur

Deploying Connaisseur is easy once the configuration is completed. Set your Kubernetes context to the correct cluster and run:

```bash
make install
```

Your output should look something like the following:

```bash
bash helm/certs/gen_certs.sh
Generating RSA private key, 4096 bit long modulus (2 primes)
...++++
...............................................................................................................................................................................................................................................................................................................................................++++
e is 65537 (0x010001)
Signature ok
subject=CN = connaisseur-svc.connaisseur.svc
Getting Private key
kubectl create ns connaisseur || true
namespace/connaisseur created
kubectl config set-context --current --namespace connaisseur
Context "your-kubernetes-context" modified.
helm install connaisseur helm --wait
NAME: connaisseur
LAST DEPLOYED: Wed Oct  7 10:45:53 2020
NAMESPACE: connaisseur
STATUS: deployed
REVISION: 1
TEST SUITE: None
```

Connaisseur was successfully deployed.

## Test Connaisseur (optional)

If you were just trusting everything someone told you, you wouldn't be here looking for a tool that ensures image integrity, so don't take our word for Connaisseur working. Go ahead and try it:

`kubectl get all -n connaisseur` will show you most* of what you deployed (ConfigMaps, Secrets and MutatingWebhookConfiguration are not shown).

### Deploy (un)signed images

Let's test if our configuration works. We need to prepare a signed and an unsigned image and push these to a remote repository. For simplicity, we define an image path variable (host, repository and image). Below, substitute `IMAGE_PATH` with your own the values as appropriate:

```bash
# Typically, IMAGE_PATH=<YOUR-REGISTRY>/<YOUR-REPOSITORY-NAME-/-DOCKER-HUB-ID>/<IMAGE-NAME>
IMAGE_PATH=docker.io/securesystemsengineering/testimage
```

We start with the signed image and use the `Dockerfile` in `connaisseur/setup` as sample:

```bash
cd setup
DOCKER_CONTENT_TRUST=0 docker build -f Dockerfile -t ${IMAGE_PATH}:signed .
DOCKER_CONTENT_TRUST=1 docker push ${IMAGE_PATH}:signed
```

> You can also use the `--disable-content-trust` flag in Docker in exchange for the environment variable.

During the push step, you will be asked to create repository key (unless you already pushed signed images to the repository in the past). We disabled DCT in the first step to not validate the signature of the base image. This will ultimately depend on whether you use signed or unsigned base images when building yours and is independent of Connaisseur. Next we build and push the unsigned image. Optionally, you might want to edit the `Dockerfile`, e.g. the text in the `echo`, to also confirm that the different digests are validated.

```bash
DOCKER_CONTENT_TRUST=0 docker build -f Dockerfile -t ${IMAGE_PATH}:unsigned .
DOCKER_CONTENT_TRUST=0 docker push ${IMAGE_PATH}:unsigned
```

We can check if everything works via `docker trust inspect --pretty ${IMAGE_PATH}` and should get something like:

```bash
Signatures for docker.io/securesystemsengineering/testimage

SIGNED TAG          DIGEST                                                             SIGNERS
signed              0c5d7013f91c03a2e87c29439ecfd093527266d92bfb051cab2103b80791193a   (Repo Admin)

Administrative keys for docker.io/securesystemsengineering/testimage

  Repository Key:   130b5abbea417fea7e2a0acd2cc0a3a84f81d5b763ed82dcfaad8dceebac0b75
  Root Key:   6b35860633a0cf852670fd9b5c12ba068875f3804d6711feb16fcd74c723c816
```

Note that there is only trust data for the `signed` tag, not for `unsigned`. Let's try to deploy our fresh images to the cluster. We start with the signed image:

```bash
kubectl run signed --image=${IMAGE_PATH}:signed
```

You should be prompted that the deployment was successful:

```bash
pod/signed created
```

Finally, let's make sure that Connaisseur will not just allow deployment of any image:

```bash
kubectl run unsigned --image=${IMAGE_PATH}:unsigned
```

You should see the deployment being rejected with an error similar to:

```bash
Error from server: admission webhook "connaisseur-svc.connaisseur.svc" denied the request: could not find signed digest for image "docker.io/securesystemsengineering/testimage:unsigned" in trust data.
```

or if you pushed the unsigned image to another registry altogether:

```bash
Error from server: admission webhook "connaisseur-svc.connaisseur.svc" denied the request: no trust data for image "docker.io/securesystemsengineering/testimage:unsigned".
```

> Note that while deployment of containers is blocked, Kubernetes will still create services or other resources you might specify in a `deployment.yaml` because those do not reference an image and are thus not denied by Connaisseur. You might have to clean up denied deployments.

Your signed images were allowed through, in contrast to those unsigned ones with unknown content. DCT, not in a nutshell, but in Kubernetes!

## Cleanup

If you want to remove Connaisseur, run `make uninstall`.

In case you deployed the `signed` image above, you might want to clean that up by `kubectl delete pod signed`.

## The end

Congratulations, you have successfully deployed Connaisseur. When testing further with it, should you be missing features or run into bugs, do not hesitate to open either a Pull Request (see our [Contributing Guidelines](../CONTRIBUTING.md)) or [create an Issue](https://github.com/sse-secure-systems/connaisseur/issues/new) to let us know.

Feel free to [share your feedback](https://github.com/sse-secure-systems/connaisseur/discussions) with us and stay safe!
