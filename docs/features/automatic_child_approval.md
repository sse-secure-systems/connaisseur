# Automatic Child Approval

> :warning: This is currently an experimental feature that might unstable over time. As such, it is not part of our semantic versioning guarantees and we take the liberty to adjust or remove it with any version at any time without incrementing MAJOR or MINOR.

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

`automaticChildApproval` in `helm/values.yaml` supports the following keys:

| Key | Default | Required | Description |
| - | - | - | - |
| `enabled` | true | | `true` or `false`; when `false`, Connaisseur will disable automatic child approval |
| `ttl` | ? | | Not yet implemented. See [below](#caching-ttl) |

## Example

In `helm/values.yaml`:

```
automaticChildApproval:
  enabled: true
```

## Additional notes

### Caching TTL

It is planned to implement a caching by which Connaisseur might perform automatic child approval only for a limited time after creation of the parent resource.

