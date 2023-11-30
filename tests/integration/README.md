# Local Integration Test Setup

Local integration testing should be easy if you're running a minikube cluster with the docker driver or a kind cluster. Just run

`./tests/integration/run_integration_tests.sh -h`

from the root folder and start from there!

## Example

If you have

- a running kind cluster and want to run the regular and the cosign integration test and you want to preserve the logs in failure case to `../integration_test_logs` you need to run

        ./tests/integration/run_integration_tests.sh -c kind -r "regular cosign" -p ../integration_test_logs

    specifying the `-c` (cluster), `-r` (run-only) and the `-p` (preserve-logs) flags

- a running minikube cluster and you want to run everything including the self-hosted-notary test but not the load and the complexity test you need to run


        ./tests/integration/run_integration_tests.sh -s "load complexity" -e

    specifying the `-s` (skip) and the `-e` (extended) flag. As the cluster defaults to minkube, it's not necessary to provide the `-c` flag.
