# Welcome to Connaisseur

A Kubernetes admission controller to integrate container image signature verification and trust pinning into a cluster.

## What is Connaisseur?

Connaisseur ensures integrity and provenance of container images in a Kubernetes cluster.
To do so, it intercepts resource creation or update requests sent to the Kubernetes cluster, identifies all container images and verifies their signatures against pre-configured public keys.
Based on the result, it either accepts or denies those requests.

Connaisseur is developed under three core values: *Security*, *Usability*, *Compatibility*.
It is built to be extendable and currently aims to support the following signing solutions:

- [Notary (V1)](https://github.com/theupdateframework/notary) / [Docker Content Trust](https://docs.docker.com/engine/security/trust/)
- [sigstore](https://sigstore.dev/) / [Cosign](https://github.com/sigstore/cosign)
- [Notary V2](https://github.com/notaryproject/nv2) (PLANNED)

It provides several additional features:

- [Metrics](features/metrics.md): *get prometheus metrics at `/metrics`*
- [Alerting](features/alerting.md): *send alerts based on verification result*
- [Detection Mode](features/detection_mode.md): *warn but do not block invalid images*
- [Namespaced Validation](features/namespaced_validation.md): *restrict validation to dedicated namespaces*
- [Automatic Child Approval](features/automatic_child_approval.md): *configure approval of Kubernetes child resources*

Feel free to reach out via [GitHub Discussions](https://github.com/sse-secure-systems/connaisseur/discussions)!

## Quick start

Getting started to verify image signatures is only a matter of minutes:

![](assets/connaisseur_demo.gif)

> :warning: Only try this out on a test cluster as deployments with unsigned images will be blocked. :warning:

Connaisseur comes pre-configured with public keys for its own repository and [Docker's official images](https://docs.docker.com/docker-hub/official_images/) (official images can be found [here](https://hub.docker.com/search?q=&type=image&image_filter=official)).
It can be fully configured via `helm/values.yaml`.
For a quick start, clone the Connaisseur repository:

```bash
git clone https://github.com/sse-secure-systems/connaisseur.git
```

Next, install Connaisseur via [Helm](https://helm.sh):

```bash
helm install connaisseur helm --atomic --create-namespace --namespace connaisseur
```

Once installation has finished, you are good to go.
Successful verification can be tested via official Docker images like `hello-world`:

```bash
kubectl run hello-world --image=docker.io/hello-world
```

Or our signed `testimage`:

```bash
kubectl run demo --image=docker.io/securesystemsengineering/testimage:signed
```

Both will return `pod/<name> created`. However, when trying to deploy an unsigned image:

```bash
kubectl run demo --image=docker.io/securesystemsengineering/testimage:unsigned
```

Connaisseur denies the request and returns an error `(...) Unable to find signed digest (...)`. Since the images above are signed using Docker Content Trust, you can inspect the trust data using `docker trust inspect --pretty <image-name>`.

To uninstall Connaisseur use:

```bash
helm uninstall connaisseur --namespace connaisseur
```

Congrats :tada: you just validated the first images in your cluster!
To get started configuring and verifying your own images and signatures, please follow our [setup guide](getting_started.md).


## How does it work?

Integrity and provenance of container images deployed to a Kubernetes cluster can be ensured via digital signatures.
On a very basic level, this requires two steps:

1. Signing container images *after building*
2. Verifying the image signatures *before deployment*

Connaisseur aims to solve step two.
This is achieved by implementing several *validators*, i.e. configurable signature verification modules for different signing solutions (e.g. Notary V1).
While the detailed security considerations mainly depend on the applied solution, Connaisseur in general verifies the signature over the container image content against a trust anchor or *trust root* (e.g. public key) and thus let's you ensure that images have not been tampered with (integrity) and come from a valid source (provenance).

![](./assets/sign-verify.png)

### Trusted digests

But what is actually verified?
Container images can be referenced in two different ways based on their registry, repository, image name (`<registry>/<repository>/<image name>`) followed by either tag or digest:

- tag: *docker.io/library/nginx:****1.20.1***
- digest: *docker.io/library/nginx@****sha256:af9c...69ce***

While the tag is a mutable, human readable description, the digest is an immutable, inherent property of the image, namely the SHA256 hash of its content.
This also means that a tag can correspond to varying digests whereas digests are unique for each image.
The container runtime (e.g. containerd) compares the image content with the received digest before spinning up the container.
As a result, Connaisseur just needs to make sure that only *trusted digests* (signed by a trusted entity) are passed to the container runtime.
Depending on how an image for deployment is referenced, it will either attempt to translate the tag to a trusted digest or validate whether the digest is trusted.
How the digest is signed in detail, where the signature is stored, what it is verfied against and how different image distribution and updating attacks are mitigated depends on the signature solutions.

### Mutating admission controller

How to validate images *before* deployment to a cluster?
The [Kubernetes API](https://kubernetes.io/docs/concepts/overview/kubernetes-api/) is the fundamental fabric behind the control plane.
It allows operators and cluster components to communicate with each other and, for example, query, create, modify or delete Kubernetes resources.
Each request passes through several phases such as authentication and authorization before it is persisted to *etcd*.
Among those phases are two steps of [admission control](https://kubernetes.io/docs/reference/access-authn-authz/admission-controllers/): mutating and validating admission.
In those phases the API sends admission requests to configured webhooks (admission controllers) and receives admission responses (admit, deny, or modify).
Connaisseur uses a mutating admission webhook, as requests are not only admitted or denied based on the validation result but might also require modification of contained images referenced by tags to trusted digests.
The webhook is configured to only forward resource creation or update requests to the Connaisseur service running inside the cluster, since only deployments of images to the cluster are relevant for signature verification.
This allows Connaisseur to intercept requests before deployment and based on the validation:

- *admit* if all images are referenced by trusted digests
- *modify* if all images can be translated to trusted digests
- *deny* if at least one of the requested images does not have a trusted digest

![](./assets/admission-controller.png)

### Image policy and validators

Now, how does Connaisseur process admission requests?
A newly received request is first inspected for container image references that need to be validated (1).
The resulting list of images referenced by tag or digest is passed to the image policy (2).
The image policy matches the identified images to the configured validators and corresponding trust roots (e.g. public keys) to be used for verification.
Image policy and validator configuration form the central logic behind Connaisseur and are described in detail und [basics](./basics.md).
Validation is the step where the actual signature verification takes place (3).
For each image, the required trust data is retrieved from external sources such as Notary server, registry or sigstore transparency log and validated against the pre-configured trust root (e.g. public key).
This forms the basis for deciding on the request (4).
In case no trusted digest is found for any of the images (i.e. either no signed digest available or no signature matching the public key), the whole request is denied.
Otherwise, Connaisseur translates all image references in the original request to trusted digests and admits it (5).

![](./assets/connaisseur-overview.png)

## Compatibility

Supported signature solutions and configuration options are documented under [validators](./validators/README.md).

Connaisseur supports Kubernets v1.16 and higher. It is expected to be compatible with most Kubernetes services and has been successfully tested with:

- [K3s](https://github.com/rancher/k3s) ✅
- [kind](https://kind.sigs.k8s.io/) ✅
- [MicroK8s](https://github.com/ubuntu/microk8s) ✅ (enable DNS addon via `sudo microk8s enable dns`)
- [minikube](https://github.com/kubernetes/minikube) ✅
- [Amazon Elastic Kubernetes Service (EKS)](https://docs.aws.amazon.com/eks/) ✅
- [Azure Kubernetes Service (AKS)](https://docs.microsoft.com/en-us/azure/aks/) ✅
- [Google Kubernetes Engine](https://cloud.google.com/kubernetes-engine/docs/) ✅
- [SysEleven MetaKube](https://docs.syseleven.de/metakube) ✅

All registry interactions use the [OCI Distribution Specification](https://github.com/opencontainers/distribution-spec/blob/main/spec.md) that is based on the [Docker Registry HTTP API V2](https://docs.docker.com/registry/spec/api/) which is the standard for all common image registries.
For using Notary (V1) as a signature solution, only some registries provide the required Notary server attached to the registry with e.g. shared authentication.
Connaisseur has been tested with the following Notary (V1) supporting image registries:

- [Docker Hub](https://hub.docker.com/) ✅
- [Harbor](https://goharbor.io/) ✅
- [Azure Container Registry (ACR)](https://docs.microsoft.com/en-us/azure/container-registry/) ✅ (check our [configuration notes](./validators/notaryv1.md#using-azure-container-registry))

In case you identify any incompatibilities, please [create an issue](https://github.com/sse-secure-systems/connaisseur/issues/new/choose) :hearts:

## Versions

The latest stable version of Connaisseur is available on the [`master`](https://github.com/sse-secure-systems/connaisseur) branch.
[Releases](https://github.com/sse-secure-systems/connaisseur/releases) follow [semantic versioning](https://semver.org/) standards to facilitate compatibility.
For each release, a signed container image tagged with the version is published in the [Connaisseur Docker Hub repository](https://hub.docker.com/repository/docker/securesystemsengineering/connaisseur).
Latest developments are available on the [`develop`](https://github.com/sse-secure-systems/connaisseur/tree/develop) branch, but should be considered unstable and no pre-built container image is provided.

## Development

Connaisseur is open source and open development.
We try to make major changes transparent via [*Architecture Decision Records* (ADRs)](./adr/README.md) and announce developments via [GitHub Discussions](https://github.com/sse-secure-systems/connaisseur/discussions/categories/announcements).
Information on responsible disclosure of vulnerabilities and tracking of past findings is available in the [Security Policy](./SECURITY.md).
Bug reports should be filed as [GitHub issues](https://github.com/sse-secure-systems/connaisseur/issues/new?assignees=&labels=&template=bug_report.md&title=) to share status and potential fixes with other users.

We hope to get as many direct contributions and insights from the community as possible to steer further development.
Please refer to our [contributing guide](CONTRIBUTING.md), [create an issue](https://github.com/sse-secure-systems/connaisseur/issues/new/choose) or [reach out to us via GitHub Discussions](https://github.com/sse-secure-systems/connaisseur/discussions) :pray:

## Wall of fame

Thanks to all the fine people directly contributing commits/PRs to Connaisseur:

<a href="https://github.com/sse-secure-systems/connaisseur/graphs/contributors">
  <img src="https://contributors-img.web.app/image?repo=sse-secure-systems/connaisseur" />
</a>

Big shout-out also to all who support the project via issues, discussions and feature requests :pray:

## Resources

Several resources are available to learn more about Connaisseur and related topics:

- "[*Container Image Signatures in Kubernetes*](https://medium.com/sse-blog/container-image-signatures-in-kubernetes-19264ac5d8ce)" - blog post (full introduction)
- "[*Integrity of Docker images*](https://berlin-crypto.github.io/event/dockerimagesignatures.html)" - talk at Berlin Crypto Meetup (*The Update Framework*, *Notary*, *Docker Content Trust* & Connaisseur [live demo])
- "[*Verifying Container Image Signatures from an OCI Registry in Kubernetes*](https://blog.sigstore.dev/verify-oci-container-image-signatures-in-kubernetes-33663a9ec7d8)" - blog post (experimental support of *sigstore*/*Cosign*)
- "[*Verify Container Image Signatures in Kubernetes using Notary or Cosign or both*](https://medium.com/sse-blog/verify-container-image-signatures-in-kubernetes-using-notary-or-cosign-or-both-c25d9e79ec45)" - blog post (Connaisseur v2.0 release)
