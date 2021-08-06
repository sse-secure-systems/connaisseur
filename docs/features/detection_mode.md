# Detection Mode

A detection mode is available in order to avoid interruptions of a running cluster, to support initial rollout or for testing purposes.
In detection mode, Connaisseur admits all images to the cluster, but issues a warning[^1] and logs an error message for images that do not comply with the policy or in case of other unexpected failures:

[^1]: The feature to send warnings to API clients as shown above was only [introduced in Kubernetes v1.19](https://kubernetes.io/blog/2020/09/03/warnings/#:~:text=In%20Kubernetes%20v1.,response%20body%20in%20any%20way.&text=The%20k8s.io%2Fclient%2Dgo%20behavior%20can%20be%20overridden,%2Dprocess%20or%20per%2Dclient.). However, warnings are only surfaced by `kubectl` in `stderr` to improve usability. Except for testing purposes, the respective error messages should either be handled via the cluster's log monitoring solution or by making use of Connaisseur's [alerting feature](alerting.md).

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

