# Validation

This document describes the image validation process as employed by Connaisseur.

Since Connaisseur is a Kubernetes AdmissionController it operates on requests and has these requests, the Kubernetes API, the registry and the notary to work with. First off, Connaisseur does some light checks on the semantics of the request it receives, e.g. whether it is capable of using the API version of the admission request.

Then it parses images to deploy from the request. Connaisseur does this for Pods, Jobs, CronJobs, Deployments, DaemonSets, StatefulSets, ReplicaSets and ReplicationControllers. These images are then validated as follows:

1. If the image is deployed as part of an already deployed object (i.e. a Pod gets deployed as a child of a Deployment and the Deployment was already validated), it will be admitted. This is done as the parent (and thus the child) might have been mutated, which could lead to duplicate validation or rule mismatch. For example, given a Deployment which contains Pods with `image:tag` that gets mutated to contain Pods with `image@sha256:digest`. Then a) the Pod would not need another validation as the image was validated during the admittance of the Deployment and b) if there exists a specific rule for `image:tag` and another for `image:*`, then after mutating the Deployment, the Pod would be falsely validated against `image:*` instead of `image:tag`. To ensure the child resource is legit in this case, the parent resource is requested via the Kubernetes API and only those images it lists are accepted.
2. The best matching rule from the image policy is looked up and if `verify: false`, the image is admitted.
3. Trust data of the image is consulted as described in the next section.

## Validation of trust data

Validation of trust data on a high level boils down to two steps:

1. Get all trusted (i.e. signed) image digests related to the tag or digest of the image.
2. If there is exactly one, admit the image.

Regarding the latter step, rejection upon no matching trusted digests is obvious. However, Connaisseur also needs to reject the image if there is more than one trusted digest, since at this point in time Connaisseur doesn't have the ability to distinguish between the right and wrong trusted digest. This only occurs in some edge cases, but nonetheless has to be addressed.

Let's now focus on the integral part of Connaisseur that is how to get all trusted digests for an `image:tag` or `image:digest` combination:

Connaisseur looks up trust data of the image in the `root`, `snapshot`, `timestamp` and `targets` files by querying the API of the notary server. Trust data syntax is validated against [their known schemas](https://github.com/sse-secure-systems/connaisseur/tree/master/connaisseur/res) (for an introduction to the trust data formats see the [presentation of our colleague Philipp Belitz](https://berlin-crypto.github.io/assets/Berlin%20Crypto%20Connaisseur.pdf)). Then, the files' signatures are validated against the pinned root key for the `root` file and against the respective keys validated in previous steps for later files. Connaisseur further gathers trust data of potential delegations linked in the `targets` file.

At this point, Connaisseur is left with a set of potentially disjoint or overlapping sets of trust data. Connaisseur filters the trust data for digests that actually relate to the image under validation.

If the image policy rule that governs the image to be validated does contain a `delegations` field, Connaisseur makes sure that all delegations' sets of trust data do contain an entry for the image. If that is not the case, the request is rejected. Subsequently, Connaisseur builds a set over the union of the digests and proceeds with step 2., i.e. accepeting if the size of the resulting set equals 1.
