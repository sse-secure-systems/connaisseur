# Detection Mode

A detection mode is available in order to avoid interruptions of a running cluster, to support initial rollout or for testing purposes.
In detection mode, Connaisseur admits all images to the cluster, but issues a warning and logs an error message for images that do not comply with the policy or in case of other unexpected failures:

```bash
kubectl run unsigned --image=docker.io/securesystemsengineering/testimage:unsigned
> Warning: Unable to find signed digest for image docker.io/securesystemsengineering/testimage:unsigned. (not denied due to DETECTION_MODE)
> pod/unsigned created
```

To activate the detection mode, set the `detectionMode` flag to `true` in `helm/values.yaml`.

## Configuration options

`detectionMode` in `helm/values.yaml` supports the following keys:

| Key | Default | Required | Description |
| - | - | - | - |
| `detectionMode` | false | | `true` or `false`; when detection mode is enabled, Connaisseur will warn but not deny requests with untrusted images. |

## Example

In `helm/values.yaml`:

```
detectionMode: true
```

