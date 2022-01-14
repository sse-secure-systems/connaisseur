# Local Integration Test Setup

## minikube

To load the required docker images into the minikube docker daemon run

```shell
eval $(minikube docker-env)
make docker
```

which will change the environment variables that specify the docker daemon to point to minikube instead of your system docker daemon.

### Preparation for minikube with virtualbox driver

Assuming you have a running minikube cluster using the virtualbox driver set as current kubernetes context you just need to have the alerting interface running.

Run the docker container that serves as alerting endpoint and retrieve the IP address that it has on the `bridge` network:

```shell
docker run -d --name alerting-endpoint -p 56243:56243 docker.io/securesystemsengineering/alerting-endpoint:latest
export ALERTING_ENDPOINT_IP=$(docker container inspect alerting-endpoint | jq -r .[].NetworkSettings.Networks.bridge.IPAddress)
```

### Preparation for minikube with docker driver

Assuming you have a running minikube cluster using the docker driver set as current kubernetes context you need to have the alerting interface running and attach the container to the network that is used by minikube to facilitate communication. By default, this network is named `minikube`, so change the minikube network name to your specific name if you use a customized one:

```shell
MINIKUBE_NETWORK=$(docker container inspect minikube | jq -r '.[].NetworkSettings.Networks | to_entries | .[].key')
docker run -d --name alerting-endpoint -p 56243:56243 docker.io/securesystemsengineering/alerting-endpoint:latest
docker network connect ${MINIKUBE_NETWORK} alerting-endpoint
export ALERTING_ENDPOINT_IP=$(docker container inspect alerting-endpoint | jq -r --arg minikube_network ${MINIKUBE_NETWORK} '.[].NetworkSettings.Networks[$minikube_network].IPAddress')
```

### Actual test

From the git repository folder run the `tests/integration/integration-test.sh` script with the name of the test you want to run, for example `regular`, `cosign` or `load` (see [the test script for all possible values](integration-test.sh)).

To cleanup the mocked alerting interface container don't forget running

```shell
docker stop alerting-endpoint
docker rm alerting-endpoint
```

## kind

For kind we assume you have a running `kind` cluster set as current kubernetes context. To load the required docker image onto the `kind` nodes, run

```shell
make docker
kind load docker-image $(yq e '.deployment.image' helm/values.yaml)
```

You need to have the alerting interface running and attach it to the docker network that is used by the kind container just as for minikube using the docker driver. By default, it's name is `kind`, so if you renamed the docker network of the kind container, provide your custom name as `KIND_NETWORK`:

```shell
KIND_NETWORK=kind
docker run -d --name alerting-endpoint -p 56243:56243 docker.io/securesystemsengineering/alerting-endpoint:latest
docker network connect ${KIND_NETWORK} alerting-endpoint
export ALERTING_ENDPOINT_IP=$(docker container inspect alerting-endpoint | jq -r --arg kind_network ${KIND_NETWORK} '.[].NetworkSettings.Networks[$kind_network].IPAddress')
```

From the git repository folder run the `tests/integration/integration-test.sh` script with the name of the test you want to run, for example `regular`, `cosign` or `load` (see [the test script for all possible values](integration-test.sh)).

Obviously, we don't want to leave unused resources running, so stop and remove the alerting interface docker container as in the minikube case :-)

```shell
docker stop alerting-endpoint
docker rm alerting-endpoint
```

## Note

The integration test only works correctly if the alerting endpoint container is set up freshly as it counts all hits to its endpoints. So cleaning up is not only housekeeping, but also prevents issues caused by double-use of the container.
