# Validation Mode

Validation mode allows configuration whether Connaisseur mutates image references (tags to trusted digests).

In default behavior during validation, Connaisseur uses the image reference (tag or digest) from the admission request to identify a trusted digest (digest with valid signature from a configured trust root) and modifies the reference to the trusted digest if one exists or denies the request otherwise.
This ensures that the container runtime pulls and spins up a container of a validated image, as the digest is an immutable inherent property of the image.

However, some closed-loop deployment technologies such as [Argo CD](https://argo-cd.readthedocs.io/) verify that the created resources correspond to the requested resources, essentially synchronizing the state from a reference repository.
In consequence, a mutated image reference causes an error for such tools, as actual and requested resource differ.
To resolve this, it is possible to configure Connaisseur to only validate but not mutate image references by which the original image reference (tag or digest) remains unchanged and successful admission only indicates that a trusted digest exists.
However, image tag and digest are only loosly associated which introduces a [*time-of-check to time-of-use* vulnerability](https://en.wikipedia.org/wiki/Time-of-check_to_time-of-use): an attacker slips in a malicious image after Connaisseur validated that a given tag exhibits a signed digest but before the runtime resolves the tag for pulling the image.
This supposedly small time window might be significantly larger if images are re-pulled by the container runtime at a later time for some reason.

To disable image mutation, set the `validationMode.mutateImage` flag to `false` in `helm/values.yaml`.

## Configuration options

`validationMode` in `helm/values.yaml` supports the following keys:

| Key | Default | Required | Description |
| - | - | - | - |
| `mutateImage` | true | | `true` or `false`; mutate image reference to trusted digest (`true`) or keep original reference (`false`) |

## Example

In `helm/values.yaml`:

```
validationMode:
  mutateImage: true
```

