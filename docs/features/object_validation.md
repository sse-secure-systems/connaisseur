# Object Validation

Object validation allows restricting validation to specific objects, and can operate alongside [namespace validation](./namespaced_validation.md).
Connaisseur can optionally include/exclude the verification trust of images based on pod labels.
This can allow for careful exception to a cluster/namespace-wide policy, when altering the image value for particular pods (*potentially self-referential containers which use their tags to determine application version*) can be problematic.

> :warning: Enabling object validation, allows roles with edit permissions on objects to disable validation for those namespaces. :warning:

Object validation offers two modes:

- `ignore`: ignore all objects with label `securesystemsengineering.connaisseur/webhook: ignore`
- `validate`: only validate objects with label `securesystemsengineering.connaisseur/webhook: validate`

The desired objects must be labelled accordingly, using the `.spec.template.metadata.labels` field of whichever controller (*deployment, statefulset, etc*) creates them.

Configure object validation via the `objectValidation` in `helm/values.yaml`.

## Configuration options

`objectValidation` in `helm/values.yaml` supports the following keys:

| Key | Default | Required | Description |
| - | - | - | - |
| `enabled` | false | | `true` or `false`; enable object validation otherwise images in all objects will be validated. |
| `mode` | ignore | | `ignore` or `validate`; configure mode of exclusion to either ignore all objecst with label `securesystemsengineering.connaisseur/webhook` set to `ignore` or only validate objects with the label set to `validate`. |

## Example

In `helm/values.yaml`:

```
objectValidation:
  enabled: true
  mode: ignore
```

Labelling target object to be excluded from validation:

```
spec:
  template:
    metadata:
      labels:
        securesystemsengineering.connaisseur/webhook: ignore
```

