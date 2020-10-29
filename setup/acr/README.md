# Connaisseur with AKS and ACR
This guide will show you how to set up Connaisseur on your Azure Kubernetes Service (AKS) cluster using the Azure Container Registry (ACR) as both the registry and the notary.

# Requirements

For this tutorial, we assume you have a working AKS cluster and an ACR with [enabled Docker Content Trust](https://docs.microsoft.com/en-us/azure/container-registry/container-registry-content-trust#enable-registry-content-trust).

> This requires the `Premium` version of ACR. If you do not wish to use the ACR as either registry or notary, use the [general setup guide](../README.md).

Your AKS cluster [should be authenticated to pull images from your ACR](https://docs.microsoft.com/en-us/azure/aks/cluster-container-registry-integration) (you can also use pull secrets instead of integrating both components, in which case some commands of the general setup guide might need small adaptations). Your Azure Active Directory user will need the `AcrImageSigner` role assignment for the ACR, otherwise you will not be able to push signed images to it.

Furthermore, we assume you have `az`, `docker`, `git`, `helm`, `jq`,  `kubectl` and `make` installed and ready to use in your CLI, i.e. you executed `az acr login`, `az aks get-credentials` and `kubectl use-context` to login to the ACR and switch to the appropriate Kubernetes context.

> The tutorial was tested on a machine running Ubuntu 20.04, but since we're not doing much of anything client-side pretty much any other OS should work as well.

# Setting up Connaisseur

For the most part, this tutorial will be the same as [for a regular Kubernetes cluster](../README.md). However, the setup for ACR is a bit different from how it would usually be used. Interactions with the ACR usually happen via the CLI that has previously been authenticated with `az acr login --name YOUR-REGISTRY`. Currently, Connaisseur only support BasicAuth for connecting to a registry, so the default authentication schemes for both tools are incompatible. Hence, we need to work around this fact by providing a username/password combination to Connaisseur. Additionally, Connaisseur will have to workaround a few oddities of the APIs exposed by the ACR, since these are not quite the same as for all other notaries we've encountered so far.

### 1. Get Connaisseur

First off, we'll export the variables used in this tutorial to allow you to immediately use your own names/URLs instead of relying on our default names. Below, substitute your own values as appropriate:

```bash
# You can/have to change these values to match your environment
REGISTRY_NAME=connyregistry

REGISTRY_URL=$(echo "${REGISTRY_NAME}.azurecr.io")
NOTARY_URL=$(echo "${REGISTRY_NAME}.azurecr.io")

git clone https://github.com/sse-secure-systems/connaisseur.git
cd connaisseur
```

### 2. Configure specifcs for the ACR

First we want to tell Connaisseur that the notary it connects to is the ACR. Unfortunately, the notary API exposed by ACR is slightly different from other notaries, so Connaisseur needs to know in order to adapt:

```bash
sed -i "s/isAcr: false/isAcr: true/" helm/values.yaml
```

The second specific change to be done when deploying Connaisseur in an environment with the ACR is to create a Service Principal (SP) that gives Connaisseur a username/password combination to retrieve an access token via BasicAuth:

```bash
# As above, you can change this to your liking
CONNAISSEUR_SP_NAME=connaisseur-registry-sp

# Retrieve the ID of your registry
REGISTRY_ID=$(az acr show --name ${REGISTRY_NAME} | jq -r '.id')

# Create a service principal with the Reader role on your registry
SP_CREDENTIALS=$(az ad sp create-for-rbac --name "${CONNAISSEUR_SP_NAME}" --role Reader --scopes ${REGISTRY_ID})

NOTARY_USER=$(echo ${SP_CREDENTIALS} | jq -r '.appId')
NOTARY_PASSWORD=$(echo ${SP_CREDENTIALS} | jq -r '.password')
```

> If something goes wrong with the creation of the Service Principal, check that you actually have sufficient privileges to create a Service Principal.

At this point, the adaptations specific to AKS and ACR are complete and you can continue with the [second step of the general Kubernetes guide](../README.md#2-set-up-docker-content-trust).

Once finished setting up Connaisseur, you may be interested in how to use DCT with Azure Pipelines. Further information is provided by Azure, check out [their documentation](https://docs.microsoft.com/en-us/azure/devops/pipelines/ecosystems/containers/content-trust).

Stay safe!
