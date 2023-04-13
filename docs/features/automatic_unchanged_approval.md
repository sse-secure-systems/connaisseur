# Automatic Unchanged Approval

With the feature *automatic unchanged approval* enabled, Connaisseur automatically approves any resource that is updated and doesn't change its image references.
This is especially useful when handling long living resources, with potentially out-of-sync signature data, that still need to be scaled up and down.

An example: When dealing with a deployment that has an image reference `image:tag`, this reference is updated by Connaisseur during signature validation to `image@sha256:123...`, to ensure the correct image is used by the deployment.
When scaling up or down the deployment, the image reference `image@sha256:123...` is presented to Connaisseur, due to the updated definition.
Over time the signature of the original `image:tag` may change and a new "correct" image is available at `image@sha256:456...`.
If afterwards the deployment in scaled up or down, Connaisseur will try to validate the image reference `image@sha256:123...`, by looking for it inside the signature data it receives.
Unfortunately this reference may no longer be present, due to signature updates and thus the whole scaling will be denied.

With automatic unchanged approval enabled, this is no longer the case.
The validation of `image@sha256:123...` will be skipped, as no different image is used.

This obviously has security implications, since it's no longer guaranteed that resources that are updated, have fresh and up-to-date signatures.
So use it with caution.
For that reason the feature is also disabled by default.
The creation of resources on the other hand remains unchanged and will enforce validation.

## Configuration options

`automaticUnchangedApproval` in `helm/value.yaml` under `application.features` supports the following values:

| Key | Default | Required | Description |
| - | - | - | - |
| `automaticUnchangedApproval` | `false` | - | `true` or `false` ; when `true`, Connaisseur will enable automatic unchanged approval |

## Example

In `helm/values.yaml`:

```yaml
application:
  features:
    automaticUnchangedApproval: true
```
