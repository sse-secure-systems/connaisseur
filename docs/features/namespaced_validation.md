# Namespaced Validation

Namespaced validation allows restricting validation to specific namespaces.
Connaisseur will only verify trust of images deployed to the configured namespaces.
This can greatly support initial rollout by stepwise extending the validated namespaces or excluding specific namespaces for which signatures are unfeasible.

> :warning: Enabling namespaced validation, allows roles with edit permissions on namespaces to disable validation for those namespaces. :warning:

Namespaced validation offers two modes:

- `ignore`: ignore all namespaces with label `securesystemsengineering.connaisseur/webhook: ignore`
- `validate`: only validate namespaces with label `securesystemsengineering.connaisseur/webhook: validate`

The desired namespaces must be labelled accordingly, e.g. via:

```
# either
kubectl namespaces <namespace> securesystemsengineering.connaisseur/webhook=ignore
# or
kubectl namespaces <namespace> securesystemsengineering.connaisseur/webhook=validate
```

Configure namespaced validation via the `namespacedValidation` in `helm/values.yaml`.

## Configuration options

`namespacedValidation` in `helm/values.yaml` supports the following keys:

| Key | Default | Required | Description |
| - | - | - | - |
| `enabled` | false | | `true` or `false`; enable namespaced validation otherwise images in all namespaces will be validated. |
| `mode` | ignore | | `ignore` or `validate`; configure mode of exclusion to either ignore all namespaces with label `securesystemsengineering.connaisseur/webhook` set to `ignore` or only validate namespaces with the label set to `validate`. |

## Example

In `helm/values.yaml`:

```
namespacedValidation:
  enabled: true
  mode: validate
```

Labelling target namespace to be validated:

```
kubectl namespaces validateme securesystemsengineering.connaisseur/webhook=validate
```

