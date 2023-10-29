# Namespaced Validation

!!! warning
    Enabling namespaced validation, allows roles with edit permissions on namespaces to disable validation for those namespaces.
Namespaced validation allows restricting validation to specific namespaces.
Connaisseur will only verify trust of images deployed to the configured namespaces.
This can greatly support initial rollout by stepwise extending the validated namespaces or excluding specific namespaces for which signatures are unfeasible.

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

Configure namespaced validation via the `namespacedValidation` in `helm/values.yaml` under `application.features`.

## Configuration options

`namespacedValidation` in `helm/values.yaml` supports the following keys:

| Key | Default | Required | Description |
| - | - | - | - |
| `mode` | - | - | `ignore` or `validate`; configure mode of exclusion to either ignore all namespaces with label `securesystemsengineering.connaisseur/webhook` set to `ignore` or only validate namespaces with the label set to `validate`. |

If the `namespacedValidation` key is not set, all namespaces are validated.

## Example

In `helm/values.yaml`:

```yaml
application:
  features:
    namespacedValidation:
      mode: validate
```

Labelling target namespace to be validated:

```
kubectl namespaces validateme securesystemsengineering.connaisseur/webhook=validate
```

