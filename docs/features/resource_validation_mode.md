# Resource Validation Mode

Resource Validation Mode controls the admission behavior of Connaisseur, blocking only resources that match the configured type. 

## Configurations Options

Resource Validation Mode can take two different values:

- `all`: all Kubernetes resources which feature image references, such as Pods, ReplicaSets or CronJobs will be blocked in case validation fails and mutated if it succeeds
- `podsOnly`: only Pods will be blocked in case validation fails or mutated if it succeeds. All other resources won't be blocked or mutated. On failure, a warning will be displayed instead

Configure resource validation mode via the `resourceValidationMode` in `charts/connaisseur/values.yaml` under `application.features`.

The `resourceValidationMode` value defaults to `all`.