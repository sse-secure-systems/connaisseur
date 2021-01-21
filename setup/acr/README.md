# Connaisseur with AKS and ACR
This guide will show you how to set up Connaisseur on your Azure Kubernetes Service (AKS) cluster using the Azure Container Registry (ACR) as both the registry and the notary.

# Requirements

For this tutorial, we assume you have a working AKS cluster and an ACR with [enabled Docker Content Trust](https://docs.microsoft.com/en-us/azure/container-registry/container-registry-content-trust#enable-registry-content-trust).

> This requires the `Premium` version of ACR. If you do not wish to use the ACR as either registry or notary, use the [general setup guide](../README.md).

Your AKS cluster [should be authenticated to pull images from your ACR](https://docs.microsoft.com/en-us/azure/aks/cluster-container-registry-integration) (you can also use pull secrets instead of integrating both components, in which case some commands of the general setup guide might need small adaptations). Your Azure Active Directory user will need the `AcrImageSigner` role assignment for the ACR, otherwise you will not be able to push signed images to it.

Furthermore, we assume you have `az`, `docker`, `git`, `helm`, `kubectl`, `make` and `yq` (>= v4) installed and ready to use in your CLI, i.e. you executed `az acr login`, `az aks get-credentials` and `kubectl use-context` to login to the ACR and switch to the appropriate Kubernetes context.

> The tutorial was tested on a machine running Ubuntu 20.04, but since we're not doing much of anything client-side pretty much any other OS should work as well.

# Setting up Connaisseur

For the most part, this tutorial will be the same as [for a regular Kubernetes cluster](../README.md). However, the setup for ACR is a bit different from how it would usually be used. Interactions with the ACR usually happen via the CLI that has previously been authenticated with `az acr login --name YOUR-REGISTRY`. Currently, Connaisseur only support BasicAuth for connecting to a registry, so the default authentication schemes for both tools are incompatible. Hence, we need to work around this fact by providing a username/password combination to Connaisseur. Additionally, Connaisseur will have to workaround a few oddities of the APIs exposed by the ACR, since these are not quite the same as for all other notaries we've encountered so far.

### 1. Get Connaisseur

Let's get started by cloning this repository:

```bash
git clone https://github.com/sse-secure-systems/connaisseur.git
cd connaisseur
```

### 2. Configure specifics to ACR

First we want to tell Connaisseur that the notary it connects to is the ACR. Unfortunately, the notary API exposed by ACR is slightly different from other notaries, so Connaisseur needs to know in order to adapt. You can manually set `notaries[*].is_acr` to `true` in `helm/values.yaml`.

```yaml
notaries:
- name: sample-acr-notary
  host: notary.acr.io
  root_keys:
  - name: default
    key: |
      -----BEGIN PUBLIC KEY-----
      -----END PUBLIC KEY-----
  is_acr: true
```

The second specific change to be done when deploying Connaisseur in an environment with the ACR is to create a Service Principal (SP) that gives Connaisseur a username/password combination to retrieve an access token via BasicAuth. Below set `<ACR-NAME>` to your registry's name and choose `<SERVICE-PRINCIPLE-NAME>` as you like:

```bash
# Retrieve the ID of your registry
REGISTRY_ID=$(az acr show --name <ACR-NAME> --output yaml | yq read - 'id')

# Create a service principal with the Reader role on your registry
az ad sp create-for-rbac --name "<SERVICE-PRINCIPLE-NAME>" --role Reader --scopes ${REGISTRY_ID}
```

> If something goes wrong with the creation of the Service Principal, check that you actually have sufficient privileges to create a Service Principal.

Note down the `.appId` and `.password` values. These are your notary username and password, respectively. You will need them later in the setup when [configuring Notary](../README.md#configure-notary). Use the `.appId` value as your Notary username, `.password` value as password and `<ACR-NAME>.azurecr.io` as your notary URL.

At this point, the adaptations specific to AKS and ACR are complete and you can continue with the [second step of the general Kubernetes guide](../README.md#2-set-up-docker-content-trust).

Once finished setting up Connaisseur, you may be interested in how to use DCT with Azure Pipelines. Further information is provided by Azure, check out [their documentation](https://docs.microsoft.com/en-us/azure/devops/pipelines/ecosystems/containers/content-trust).

Stay safe!
