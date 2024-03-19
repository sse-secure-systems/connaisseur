# Integration Testing Script

This script is designed to facilitate integration testing for various components and features. It supports multiple test cases, each tailored to verify specific functionalities.

## Usage

To run a specific test case, use the following command:

```bash
bash test/integration/main.sh <test_case>
```

### Available Test Cases

- `regular`: Test basic functionality of all validators.
- `notaryv1`: Test the Notary v1 validator.
- `cosign`: Test the Cosign validator.
- `load`: Test system load.
- `namespaced`: Test namespace validation feature.
- `complexity`: Test complex deployments with multiple containers.
- `deployment`: Test different deployments with containers and init containers.
- `pre-config`: Test pre-configured values.yaml on deployments.
- `pre-config-and-workload`: Test pre-configured values.yaml on deployments and all workloads.
- `cert`: Test a custom TLS certificate for Connaisseur and upgradability to it.
- `redis-cert`: Test a custom TLS certificate for Redis and upgradability to it.
- `upgrade`: Test upgradability of Connaisseur.
- `alerting`: Test alerting mechanisms.
- `other-ns`: Test whether Connaisseur can be installed in non-default namespaces with limited permissions.
- `self-hosted-notary`: Test whether Connaisseur works with a self-hosted notary server.
- `all`: Runs all other test cases (except for `load`) in a loop.
