# Setup

Setting up Connaisseur for the first time can be a bit of a hassle, especially if you are not familiar with Docker Content Trust (DCT). Furthermore, Connaisseur requires/links several other services (Kubernetes cluster, container registry, notary server) for which many common providers exist. Hence, we've created multiple guides for various environments to help you on the way.

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

In `helm/values.yaml`, we first need to specify the location of the notary instance to be used. Connaisseur supports the configuration of multiple notary instances, should your image signatures reside at different locations. Per default, the official DockerHub notary is configured, with the public key for all official images, but for now let's assume you want to add a new notary instance. Simply add a new entry in the `notary` field, specifying a `name`, `host` and a list of public root keys (`root_keys`). The `name` should be unique among all notary configurations, the `host` points to the host address of the notary instance and the list of public root keys will be used to verify the image signatures residing in this notary instance. Why a list, you may ask? Just take a look at the the official DockerHub notary, where the official images are signed with a different key as your own images you can push to DockerHub. If you want to verify both, official images and your own (all residing on DockerHub), you'll need multiple keys. How to obtain these will be described further below ([here](#retrieving-the-public-root-key)).

In addition to these three mandatory settings, a self-signed certificate and authentication can be added, as well as marking a notary belonging to an Azure Container Registry (acr). The self-signed certificate can be added with the `selfsigned_cert` field, where it will be pasted in PEM format. The authentication detail can be defined in the `auth` field, where either the credentials are given directly with `auth.user` and `auth.password` or a predefined [Kubernetes secret](https://kubernetes.io/docs/concepts/configuration/secret/) is referenced in the `auth.secretName` field. The data of the predefined secret needs to be a `cred.yaml` with the fields `USER` and `PASS`. Lastly the `is_acr` can be used to mark the notary as being part of an Azure Container Registry, as these types of notaries present a slightly different kind of behavior. All in all a sample notary configuration might look like this:

```yaml
notaries:
- name: harbor
  host: notary.harbor.domain
  root_keys:
  - name: default
    key: |
      -----BEGIN PUBLIC KEY-----
      ...
      -----END PUBLIC KEY-----
  - name: app1
    key: | 
      -----BEGIN PUBLIC KEY-----
      ...
      -----END PUBLIC KEY-----
  selfsigned_cert: | 
    -----BEGIN CERTIFICATE-----
    ...
    -----END CERTIFICATE-----
  auth:
    user: notaryuser
    password: notarypassword
    # secretName: notary-secret <-- alternatively
    # the secret data needs to look like this:
    # data:
    #   cred.yaml: b46enc(USER: notaryuser\nPASS: notarypassword)
  # is_acr: true 
```

If you simply want to verify non-official images on DockerHub, then just add the corresponding public key to the existing predefined notary configuration under `root_keys`, next to the key for official images. But how do you get these public root keys?

#### Retrieving the public root key

For now let's assume you only want to verify image signatures you created/will create, using the key generated in [step two](#set-up-docker-content-trust). To get the public part of this you have to convert the key manually.

- Go to your private docker trust folder `~/.docker/trust/private` and identify the root key. To do so, you can either go through the files and search for the one with `role: root` or `grep -r 'role: root'`.
- Copy the root key file to a new file `root-priv.key` and remove line with `role: root` and the following empty line.
- Generate the corresponding public key via `openssl ec -in root-priv.key -pubout -out root.pub`. You will be asked to enter your root password.
- The new `root.pub` contains your public key which you copy and set as a new `root_keys` entry in your notary configuration of choice in `connaisseur/helm/values.yaml`. The result should look similar as in the example above.
- To clean up, remove the `root-priv.key` and `root.pub` in `~/.docker/trust/private`.

Getting the public key can also be summarized in a small script:

```bash
cd ~/.docker/trust/private
sed '/^role:\sroot$/d' $(grep -iRl "role: root$" .) > root-priv.key
openssl ec -in root-priv.key -pubout -out root.pub
```

#### Configure the image policy

Since we have potentially multiple notary instances and multiple keys for each instance, Connaisseur somehow needs to know for which images it should use what kind of combination of instance and key  (otherwise, any key compromised in your supply chain would constitute a [potential] compromise of all your images). This is configured in the `policy` part of the `helm/values.yaml`, where different rules are defined, that need to be matched against a given image. Only one rule will be matched at the same time and this rule can specify which notary should be used, with the `notary` field. The value of this field has to match one of the notary `name` fields. Additionally a `key` field can be given in the rule, which will then specify which key within the chosen notary configuration should be used. This again has to match a value of a `name` field of one of the `root_keys` entries. If no `notary` or `key` fields are given inside a rule, then Connaisseur will either do one of two things:

1. Should there only be one notary configuration or only one key defined within a given configuration, this configuration or key will be taken by default for verification purposes.
2. Should there be more then one notary configuration or key and if one of the `name` fields is set to `default`, Connaisseur will take this one. If no default is specified and no specific entry defined, Connaisseur will abort the validation with an error.

In the below example, all images coming from a `core.harbor.domain` registry will be verified using the `harbor` notary from the example above and use its `app1` key.

```yaml
policy:
- pattern: "*:*"
  verify: true
- pattern: "core.harbor.domain/*:*"
  verify: true
  notary: harbor
  key: app1
```

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

Stay safe!
