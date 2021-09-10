## CONNAISSEUR - Verify Container Image Signatures in Kubernetes

An admission controller for Kubernetes integrating container image signature verification and trust pinning into a cluster to ensure that only valid images are being deployed - simple, flexible, secure.

## What is Connaisseur?

Connaisseur ensures integrity and provenance of container images in a Kubernetes cluster.
To do so, it intercepts resource creation or update requests sent to the Kubernetes cluster, identifies all container images and verifies their signatures against pre-configured public keys.
Based on the result, it either accepts or denies those requests.

To learn more about Connaisseur, visit the [full documentation](https://sse-secure-systems.github.io/connaisseur/).


## Get started

To get started, locally add the Connaisseur [Helm](https://helm.sh/) repository 

```console
helm repo add connaisseur https://sse-secure-systems.github.io/connaisseur/charts
```

and install the Connaisseur Helm chart from there:

```console
helm install connaisseur connaisseur/connaisseur --atomic --create-namespace --namespace connaisseur
```

The default configuration of Connaisseur holds the public root key for [Docker official images](https://docs.docker.com/docker-hub/official_images/), so running such an official Docker image like the `hello-world` should succeed

```console
kubectl run hello-world --image=docker.io/hello-world
```

as Connaisseur will successfully validate the signature of the `hello-world` image against the pre-configured public key, while running an image without any signature

```
kubectl run unsigned --image=docker.io/securesystemsengineering/testimage:unsigned
```
or running an image with a signature not matching (one of) the pinned root keys

```
kubectl run foreignsignature --image=bitnami/postgresql
```

will fail.

## Discussions, support & feedback
We hope to steer development of Connaisseur from demand of the community, are excited about your feedback and happy to help if you need support! So feel free to connect with us via [GitHub Discussions](https://github.com/sse-secure-systems/connaisseur/discussions).

## Contact

You can reach us via email under [connaisseur@securesystems.dev](mailto:connaisseur@securesystems.dev).