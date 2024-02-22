# Automatic Child Approval

Per default, Connaisseur uses *automatic child approval* by which the child of a Kubernetes resource is automatically admitted without re-verification of the signature in order to avoid duplicate validation and handle inconsistencies with the image policy.
This behavior can be configured or even disabled.

When automatic child approval is enabled, images that are deployed as part of already deployed objects (e.g. a Pod deployed as a child of a Deployment) are already validated and potentially mutated during admission of the parent.
In consequence, the images of child resources are directly admitted without re-verification of the signature.
This is done as the parent (and thus the child) has already been validated and might have been mutated, which would lead to duplicate validation and could cause image policy pattern mismatch.
For example, given a Deployment which contains Pods with `image:tag` that gets mutated to contain Pods with `image@sha256:digest`.
Then a) the Pod would not need another validation as the image was validated during the admittance of the Deployment and b) if there exists a specific rule with pattern `image:tag` and another less specific rule with `image*`, then after mutating the Deployment, the Pod would be falsely validated against `image*` instead of `image:tag`.
To ensure the child resource is legit in this case, the parent resource is requested via the Kubernetes API and only those images it lists are accepted.

When automatic child approval is disabled, Connaisseur only validates and potentially mutates Pod resources.

There is trade-offs between the two behaviors:
With automatic child approval, Connaisseur only verifies that the image reference in a child resource is the same as in the parent.
This means that resources deployed prior to Connaisseur will never be validated until they are re-deployed even if a corresponding Pod is restarted.
Consequently, a restarting Pod with an expired signature would still be admitted.
However, this avoids unexpected failures when restarting Pods, avoids inconsistencies with the image policy and reduces the number of validations and thus the load.
Furthermore, disabling automatic child approval also means that deployments with invalid images will be successful even though the Pods are denied.

The extension of the feature (disabling, caching) is currently under development to improve security without compromising on usability.

## Configuration options

`automaticChildApproval` in `charts/connaisseur/values.yaml` under `application.features` supports the following values:

| Key | Default | Required | Description |
| - | - | - | - |
| `automaticChildApproval` | `true` | - | `true` or `false`; when `false`, Connaisseur will disable automatic child approval |
| `automaticChildApproval.ttl` | ? | - | Not yet implemented. See [below](#caching-ttl). If set, will enable automatic child approval |

## Example

In `charts/connaisseur/values.yaml`:

```yaml
application:
  features:
    automaticChildApproval: true
```

## Additional notes

### Caching

Connaisseur implements a caching mechanism, which allows bypassing verification for images that were already admitted recently.
One might think that this obviates the need for automatic child approval.
However, since an image may be mutated during verification, i.e. a tag being replaced with a digest, the child resource image to be validated could be different from the original one and in that case could be governed by a different policy pattern that explicitly denies the specific digest in which case caching would change the outcome, if we cached the validation result for both original and mutated image.
As such, caching cannot replace automatic child approval with regards to skipping validations even though they both admit workload objects with images that were "already admitted".


### Pod-only validation

If the resource validation mode is set to only validate pods, while automatic child approval is enabled, then the combination becomes an allow-all validator with regards to all workloads except for individual pods.
As this is unlikely to be desired, we pretend automatic child approval were disabled if it is enabled in conjunction with a pod-only resource validation mode.
