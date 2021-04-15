# Advanced Use-Cases

This document details some more advanced use-cases of Connaisseur.

## Delegation feature

Signatures in Docker Content Trust or Notary v1 are based on [The Update Framework (TUF)](https://github.com/theupdateframework/specification). TUF allows delegating signature permissions to other people. Connaisseur supports requiring delegations for Notary v1 via the `policy` definition:

### Image Policy Example

Let's say you have an organizational root key pinned in the [helm/values.yaml](helm/values.yaml), which you use to delegate to individual developers, i.e. via `docker trust key load delegation.key --name charlie` (see [the Docker documentation](https://docs.docker.com/engine/security/trust/trust_delegation/) for the docker CLI commands).

Now, given an image policy

```yaml
policy:
  - pattern: "*:*"
```

the signature of every single developer to whom you delegated signature rights will be considered valid. That might be fine for most use-cases, but for `trusted-thing`, which runs as a privileged container on all k8s nodes, you really want to limit yourself to Alice from the security team, whom you trust to have properly reviewed it. And also to Bob, your most senior developer, because they got that eye for detail and they really don't do the "It's friday, force push master, I'm outta here" stuff, that Charlie did last month... Anyways, Connaisseur can handle this:

```yaml
policy:
  - pattern: "*:*"
  - pattern: "your.org/trusted-thing:*"
    delegations: ["alice", "bob"]
```

Connaisseur will make sure, that both Alice and Bob have a current signature on the same digest for any tagged `trusted-thing` image you deploy.
If one of their signatures is missing or if they point to different digests for the same tag, Connaisseur will block the deployment.
In the meantime, for all other images any delegated individual key, repository key or the root key will be accepted.

The list you add in the `delegations` field can contain any number of delegations. Just remember that it is a logical `AND`, so _all_ delegations will have to verify correctly. 

Another potential use-case is to use delegations to sign an image in various stages of your CI, i.e. requiring the signature of your linter, your security scanner and your software lisence compliance check.

### Limits

Q: Is a logical `OR` possible? Are there n-of-m thresholds? Is there `insert-arbitrary-logical-function`?

A: No, currently not. If you have the use-case, feel free to [hit us up](https://github.com/sse-secure-systems/connaisseur/discussions), [open an issue](https://github.com/sse-secure-systems/connaisseur/issues/new/choose) or open a pull request.

Q: Will delegations work with Cosign or Notary v2?

A: Currently, Cosign does not natively support delegations, so Connaisseur doesn't either. For Notary v2, it looks like they will support delegations and so Connaisseur will most likely support them as in Notary v1.