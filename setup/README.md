# Setup

Setting up Connaisseur for the first time can be a bit of a hassle, especially if you are not familiar with Docker Content Trust (DCT). Furthermore, Connaisseur requires/links several other services (Kubernetes cluster, container registry, notary server) for which many common providers exist. Hence, we've created multiple guides for various environments to help you on the way.

The guide below offers a simple default configuration for setting up Connaisseur using public infrastructure and is aimed at quick testing. It uses [Docker Hub](https://hub.docker.com/) as both container registry and notary, but is expected to work for other solutions as well. It has been tested for the following Kubernetes services:
- [x] [MicroK8s](https://github.com/ubuntu/microk8s)
- [x] [minikube](https://github.com/kubernetes/minikube)
- [x] [Azure Kubernetes Service (AKS)](https://docs.microsoft.com/en-us/azure/aks/)
- [x] [Amazon Elastic Kubernetes Service (EKS)](https://docs.aws.amazon.com/eks/)
- [x] [Google Kubernetes Engine](https://cloud.google.com/kubernetes-engine/docs/)
- [x] [SysEleven MetaKube](https://docs.syseleven.de/metakube)

Two further specialized guides exist:
1. **Local setup ([Minikube](https://github.com/kubernetes/minikube) & [Harbor](https://github.com/goharbor/harbor))**: Connaisseur can be run completely locally with a minikube instance paired with a local Harbor installation that combines registry and notary servers. This setup is a bit more cumbersome since it does not use existing public infrastructure such as PKI. However, it is entirely based on open-source solutions, does not require continuous access to the internet and you control every part of the installation. This makes it specifically suited e.g. for security researchers and users interested in the inner workings of DCT and Connaisseur. Head over to [the respective README](local/README.md) to try it out.
2. **[Azure Kubernetes Services](https://docs.microsoft.com/en-us/azure/aks/) with [Azure Container Registry (ACR)](https://docs.microsoft.com/en-us/azure/container-registry/)**: Microsoft Azure is currently the only one of the big cloud providers with a managed Kubernetes and container registry that supports DCT. If you want to set up Connaisseur with ACR, head over to [the specialized setup guide](acr/README.md).


## Requirements

We assume you have a running Kubernetes cluster already. Since this tutorial works with the CLI, we furthermore assume you have the `docker`, `git`, `helm`, `kubectl`, `make` binaries installed and usable, i.e. having run `docker login` and having switched to the appropriate `kubectl` context.

> **MicroK8s**: DNS addon must be activated using `sudo microk8s enable dns`.

> This tutorial was tested on a machine running Ubuntu 20.04.

## Configuration and installation of Connaisseur

### 1. Set up environment

First off, we'll export the variables used in this tutorial to allow you to immediately use your own names/URLs instead of relying on our default names. Below, substitute your own values as appropriate (ideally use lowercase letters for compatibility with Docker):

```bash
IMAGE_PATH=docker.io/testingconny/testimage

NOTARY_URL=notary.docker.io
NOTARY_USER=<YOUR-NOTARY-USERNAME/DOCKER-HUB-ID>
NOTARY_PASSWORD=<YOUR-NOTARY-PASSWORD>

git clone https://github.com/sse-secure-systems/connaisseur.git
cd connaisseur
```

### 2. Set up Docker Content Trust

If you already have a root key configured on your system, you can skip this step (you can check whether there is already a root key file with `grep -iRl "role: root$" ~/.docker/trust/`).

Otherwise, generate a public-private root key pair with
 `docker trust key generate root`.

>  If you want to stick to only signed images, you can either run `export DOCKER_CONTENT_TRUST=1` or add it to your `.bashrc` (or equivalent) to (permanently) configure `docker` to _only ever_ use signed images. If you do so, you can selectively disable DCT by prefixing a single command by `DOCKER_CONTENT_TRUST=0`.

### 3. Configure Connaisseur

Before you can finally set up Connaisseur, you will need to configure its connection to the notary server provided by Docker Hub (or your notary server of choice).

> At this point, Connaisseur only supports BasicAuth for connecting to the notary.

Below is a list of commands to programmatically do the changes to the `values.yaml` file in the `helm` folder. However, you can also do these changes manually if you want. They are comprised of setting the notary server, notary credentials and the root public key for verification.

```bash
sed -i "s/host: notary.docker.io/host: ${NOTARY_URL}/" helm/values.yaml
sed -i "s/user: notaryuser/user: ${NOTARY_USER}/" helm/values.yaml
sed -i "s/password: Password123/password: ${NOTARY_PASSWORD}/" helm/values.yaml

FIRST_LINE=$(grep -n rootPubKey: helm/values.yaml | sed s/:.*//)
LAST_LINE=$(grep -nF -- '-----END PUBLIC KEY-----' helm/values.yaml | sed s/:.*//)
sed -i $((${FIRST_LINE} + 1)),${LAST_LINE}d helm/values.yaml

cd ~/.docker/trust/private
sed '/^role:\sroot$/d' $(grep -iRl "role: root$" .) > root-priv.key
openssl ec -in root-priv.key -pubout -out root-pub.pem
```
After entering your password, do further

```bash
sed -i "${FIRST_LINE}s?.*?  rootPubKey: |\n    $(sed ':a;N;$!ba;s/\n/\\n    /g' root-pub.pem)?" ${OLDPWD}/helm/values.yaml
rm root-priv.key root-pub.pem
cd -
```

> The `values.yaml` file in the `helm` folder is _the_ config file for Connaisseur. If you have some time to spare, have a look :)
>
> For example, you can turn on detection mode by running `sed -i "s/detection_mode: false/detection_mode: true/" helm/values.yaml`, which will allow your deployments to pass, but will log the violation. This might be useful when rolling out Connaisseur to an existing Kubernetes installation in order to first get a grasp on remaining obstacles before turning on (the default) blocking mode.

> What is being done at this point is to set your personal root key as Connaisseur's trust anchor. If used in production, you may wish to go for [setting up delegation keys](https://docs-stage.docker.com/engine/security/trust/trust_delegation/#creating-delegation-keys) and keep the root key away from everyday-signing.

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

### 1. Deploy (un)signed images

To test Connaisseur's capabilities go ahead and build both an unsigned and a signed image:

```bash
cd setup
DOCKER_CONTENT_TRUST=0 docker build -f Dockerfile.unsigned -t ${IMAGE_PATH}:unsigned .
DOCKER_CONTENT_TRUST=0 docker push ${IMAGE_PATH}:unsigned
DOCKER_CONTENT_TRUST=0 docker build -f Dockerfile.signed -t ${IMAGE_PATH}:signed .
DOCKER_CONTENT_TRUST=1 docker push ${IMAGE_PATH}:signed
cd -
```

During the second push, you will be asked to create repository key (unless you already pushed signed images to the repository in the past).

Then see what happens when you attempt deploying the images. First try the unsigned image:

```bash
kubectl create -f - << EOF
apiVersion: apps/v1
kind: Deployment
metadata:
  name: sample-deployment
  labels:
    app: sample
spec:
  selector:
    matchLabels:
      app: sample
  replicas: 1
  template:
    metadata:
      labels:
        app: sample
    spec:
      containers:
      - name: sample
        image: ${IMAGE_PATH}:unsigned
        imagePullPolicy: Always
        ports:
        - containerPort: 5000
---
apiVersion: v1
kind: Service
metadata:
  name: sample
  labels:
    app: sample
spec:
  ports:
  - name: port
    port: 8080
    targetPort: 5000
  selector:
    app: sample
  type: LoadBalancer
EOF
```

You should see the deployment being rejected with an error similar to

```bash
service/sample created
Error from server: error when creating "STDIN": admission webhook "connaisseur-svc.connaisseur.svc" denied the request: could not find signed digest for image "docker.io/testingconny/testimage:unsigned" in trust data.
```

> Note that while the container is blocked Kubernetes still creates the service, because it does not reference an image and is thus not denied by Connaisseur. You can clean it up by executing `kubectl delete service sample`.

Finally, make sure that Connaisseur will deploy the signed image and isn't just rejecting all images:

```bash
kubectl create -f - << EOF
apiVersion: apps/v1
kind: Deployment
metadata:
  name: sample-deployment
  labels:
    app: sample
spec:
  selector:
    matchLabels:
      app: sample
  replicas: 1
  template:
    metadata:
      labels:
        app: sample
    spec:
      containers:
      - name: sample
        image: ${IMAGE_PATH}:signed
        imagePullPolicy: Always
        ports:
        - containerPort: 5000
---
apiVersion: v1
kind: Service
metadata:
  name: sample
  labels:
    app: sample
spec:
  ports:
  - name: port
    port: 8080
    targetPort: 5000
  selector:
    app: sample
  type: LoadBalancer
EOF
```

This deployment should be accepted with

```bash
deployment.apps/sample-deployment created
service/sample created
```

Your signed images were allowed through, in contrast to those unsigned ones with unknown content. DCT, not in a nutshell, but in Kubernetes!

### 2. Cleanup

If you want to remove the test deployment of step 1, run `kubectl delete all -lapp=sample`.

## Uninstall Connaisseur

For removing Connaisseur, run `make uninstall`.

## The end

Congratulations, you have successfully deployed Connaisseur. When testing further with it, should you be missing features or run into bugs, do not hesitate to open either a Pull Request (see our [Contributing Guidelines](../CONTRIBUTING.md)) or [create an Issue](https://github.com/sse-secure-systems/connaisseur/issues/new) to let us know.

Stay safe!
