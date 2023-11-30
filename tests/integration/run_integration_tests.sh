#!/usr/bin/env bash
set -euo pipefail

RED="\033[0;31m"
GREEN="\033[0;32m"
NC="\033[0m"
SUCCESS="${GREEN}SUCCESS${NC}"
FAILED="${RED}FAILED${NC}"
SCRIPT_FAILED="${RED}SCRIPT EXITED UNEXPECTEDLY${NC}"

DEFAULT_CTX=$(kubectl config current-context)

source tests/integration/cleanup.sh

IS_INTEGRATION_TEST_RUNNING="false"
EXTENDED="false"

cleanup() {
    rv=$?
    echo "Cleanup local resources..."
    eval $(minikube docker-env --unset) >/dev/null 2>&1 || true
    docker stop alerting-endpoint notary-signer notary-server >/dev/null  2>&1 || true
    docker rm alerting-endpoint notary-signer notary-server >/dev/null 2>&1 || true
    rm .hosts >/dev/null 2>&1 || true
    rm -rf tmp >/dev/null 2>&1 || true
    echo "Finished cleanup"
    exit $rv
}

# cleanup on ^C
cleanup_on_sigint() {
    if [[ ${IS_INTEGRATION_TEST_RUNNING} == "true" ]]; then
      preserve_info_and_cleanup
    fi
}

trap "cleanup_on_sigint" SIGINT
trap "cleanup" SIGTERM EXIT

help()
{
   # Display Help
   echo "This script will run the integration test suite locally. By default, all integration tests besides of the 'self-hosted-notary' test will be run (addable with -e (extended) flag)."
   echo
   echo "Flag   Values                       Meaning         Description"
   echo "s      space-separated list         skip            Provided integration tests will be skipped. Cannot be used with -r (run-only) flag."
   echo "       of integration test names"
   echo "       as strings"
   echo "r      space-separated list         run-only        Only the provided integration tests will be run. Cannot be used with -s (skip) flag."
   echo "       of integration test names"
   echo "       as strings"
   echo "e                                   extended        Include 'self-hosted-notary' test."
   echo "c      <'minikube'|'kind'>          cluster         Specifies the cluster that should be used for integration testing. Must be either 'minikube' or 'kind'. (Default: 'minikube')"
   echo "p      <path>                       preserve-logs   Must be a valid path. If set, log files of failed tests are copied to that path."
   echo "h                                   help            Display this help."
   echo
   exit 0
}

while getopts 'hs:r:c:d:p:e' FLAG; do
  case "$FLAG" in
    h)
      help
    ;;
    s)
      if [[ "${INTEGRATION_TESTS_TO_RUN:-"not-set"}" == "not-set" ]]; then
        readarray -d ' ' -t INTEGRATION_TESTS_TO_SKIP <<< "${OPTARG}"
      else
        echo "Aborting: Please specify either the run-only (-r) or the skip (-s) flag, not both."
      fi
    ;;
    r)
      if [[ "${INTEGRATION_TESTS_TO_SKIP:-"not-set"}" == "not-set" ]]; then
      readarray -d ' ' -t INTEGRATION_TESTS_TO_RUN <<< "${OPTARG}"
      else
        echo "Aborting: Please specify either the run-only (-r) or the skip (-s) flag, not both."
        exit 1
      fi
    ;;
    c)
      CLUSTER="${OPTARG}"
      if ! [[ "${CLUSTER}" =~ ^(minikube|kind)$ ]]; then
        echo "Aborting: This script only supports local integration tests with either minikube or kind."
        exit 1
      fi
    ;;
    p)
      DESTINATION="${OPTARG}"
    ;;
    e)
      EXTENDED="true"
  esac
done
shift

mkdir tmp

export COSIGN_PUBLIC_KEY="-----BEGIN PUBLIC KEY-----<br>MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEQ70fJ/NA109p3/43cTgwnLQ+HsvK<br>jFK/0L1kLUQO+e2cL+3+y2s4IykwTxfSnqOSA0kEy1rTrhrXLCox4uRmSQ==<br>-----END PUBLIC KEY-----"

if [[ "${CLUSTER:-"minikube"}" == "minikube" ]]; then
  if [[ "$(docker inspect minikube | jq -r .[].State.Status || echo 'container not found')" != "running" ]]; then
    echo "You configured to run the tests on Minikube, but there's no running Minikube. Exiting..."
    exit 1
  fi
  eval $(minikube docker-env)
  echo "Building docker image..."
  make docker > /dev/null
  echo "Done building docker image!"
  NETWORK=$(docker container inspect minikube | jq -r '.[].NetworkSettings.Networks | to_entries | .[].key')
else
  if [[ "$(docker inspect kind-control-plane | jq -r .[].State.Status || echo 'container not found')" != "running" ]]; then
    echo "You configured to run the tests on Kind, but there's no running Kind. Exiting..."
    exit 1
  fi
  echo "Building docker image..."
  make docker > /dev/null
  echo "Done building docker image!"
  kind load docker-image $(yq e '.kubernetes.deployment.image.repository' helm/values.yaml):v$(yq e '.appVersion' helm/Chart.yaml)
  NETWORK=$(docker container inspect kind-control-plane | jq -r '.[].NetworkSettings.Networks | to_entries | .[].key')
fi

readarray -t FULL_INTEGRATION_TEST_SUITE < <(yq e -r -o=j '.jobs.[].strategy.matrix | select(.integration-test-arg) | .integration-test-arg[]' .github/workflows/.reusable-integration-test.yml)

FAILED_INTEGRATION_TESTS=()
SUCCESSFUL_INTEGRATION_TESTS=()
SCRIPT_FAILURES=()

INTEGRATION_TEST_SUITE=( "${INTEGRATION_TESTS_TO_RUN[@]:-${FULL_INTEGRATION_TEST_SUITE[@]}}" )

if ! [[ ${EXTENDED} == "true" || "${INTEGRATION_TESTS_TO_RUN[@]}" =~ "self-hosted-notary" ]]; then
  INTEGRATION_TESTS_TO_SKIP+=("self-hosted-notary")
fi

for INTEGRATION_TEST in ${INTEGRATION_TEST_SUITE[@]}; do
  if [[ "${INTEGRATION_TESTS_TO_SKIP[@]}" =~ "${INTEGRATION_TEST}" ]]; then
    echo "Skipping integration test ${INTEGRATION_TEST}"
  else
    if [[ ${INTEGRATION_TEST} == 'self-hosted-notary' ]]; then
      echo "Spinning up notary containers..."
      docker pull docker.io/securesystemsengineering/testimage:self-hosted-notary-signed
      PREFIXED_DIGEST=$(docker images --digests | grep self-hosted-notary-signed | awk '{print $3}')
      export DIGEST=$(echo ${PREFIXED_DIGEST#sha256:})
      docker run -d --name notary-signer -p 7899:7899 -v ./tests/data/notary_service_container/signer:/etc/docker/notary-signer/ --network ${NETWORK} notary:signer -config=/etc/docker/notary-signer/config.json
      NOTARY_SIGNER_IP=$(docker container inspect notary-signer | jq -r --arg network ${NETWORK} '.[].NetworkSettings.Networks[$network].IPAddress')
      docker run -d --name notary-server -p 4443:4443 --add-host notary.signer:${NOTARY_SIGNER_IP} -v ./tests/data/notary_service_container/server:/etc/docker/notary-server --network ${NETWORK} notary:server -config=/etc/docker/notary-server/config.json -logf=json
      export NOTARY_SERVER_IP=$(docker container inspect notary-server | jq -r --arg network ${NETWORK} '.[].NetworkSettings.Networks[$network].IPAddress')
      docker build --build-arg "DIGEST=${DIGEST}" -f tests/integration/Dockerfile.populate_notary . -t populate-notary
      docker run --network ${NETWORK} --add-host notary.server:${NOTARY_SERVER_IP} populate-notary
      export NOTARY_IP=${NOTARY_SERVER_IP}
      echo "Done spinning up notary..."
    elif [[ ${INTEGRATION_TEST} == 'regular' ]]; then
      echo "Spinning up mocked alerting interface..."
      docker run -d --name alerting-endpoint -p 56243:56243 docker.io/securesystemsengineering/alerting-endpoint:latest
      docker network connect ${NETWORK} alerting-endpoint
      export ALERTING_ENDPOINT_IP=$(docker container inspect alerting-endpoint | jq -r --arg network ${NETWORK} '.[].NetworkSettings.Networks[$network].IPAddress')
      echo "Done spinning up alerting interface!"
    fi
    echo "Running integration test ${INTEGRATION_TEST}..."
    mkdir "./tmp/${INTEGRATION_TEST}"
    IS_INTEGRATION_TEST_RUNNING="true" #this will be wrong when there is a failure with tee because in that case the integration test won't be started
    ./tests/integration/integration-test.sh ${INTEGRATION_TEST} |& tee ./tmp/${INTEGRATION_TEST}/test.log || true
    IS_INTEGRATION_TEST_RUNNING="false"

    echo "Done running integration test ${INTEGRATION_TEST}."
    mv connaisseur.log connaisseur.state connaisseur.conf ./tmp/${INTEGRATION_TEST}/
    if [[ "$(cat ./tmp/${INTEGRATION_TEST}/test.log)" =~ "Passed integration test." ]];then
      SUCCESSFUL_INTEGRATION_TESTS+=("${INTEGRATION_TEST}")
      rm ./tmp/${INTEGRATION_TEST}/test.log
    elif [[ "$(cat ./tmp/${INTEGRATION_TEST}/test.log)" =~ "Failed integration test." ]]; then
      FAILED_INTEGRATION_TESTS+=("${INTEGRATION_TEST}")
    else
      SCRIPT_FAILURES+=("${INTEGRATION_TEST}")
      echo "Status of integration test ${INTEGRATION_TEST} cannot be determined. Probably a script failure. Check the logs."
    fi
  fi
done

echo -e "\n\n\n#############################################\n\n\n"
echo -e "SUMMARY:\n\n"

if [[ "${#SUCCESSFUL_INTEGRATION_TESTS[@]}" != 0 ]]; then
  echo -e "${SUCCESS}: The following tests ran successfully:\n\n"
  for SUCCESSFUL_INTEGRATION_TEST in "${SUCCESSFUL_INTEGRATION_TESTS[@]}"; do
    echo "    - ${SUCCESSFUL_INTEGRATION_TEST}"
  done
  echo -e "\n\n"
fi

if [[ "${#FAILED_INTEGRATION_TESTS[@]}" != 0 ]]; then
  echo -e "${FAILED}: The following tests failed:\n\n"
  for FAILED_INTEGRATION_TEST in "${FAILED_INTEGRATION_TESTS[@]}"; do
    echo "    - ${FAILED_INTEGRATION_TEST}"
    if [[ ${DESTINATION:-""} != "" ]]; then
      mkdir -p "${DESTINATION}"
      cp -r "./tmp/${FAILED_INTEGRATION_TEST}" "${DESTINATION}/${FAILED_INTEGRATION_TEST}"
    fi
  done

  echo -e "\n\n"

  if [[ ${DESTINATION:-""} != "" ]]; then
    echo -e "Log files for failed integration tests were saved to '${DESTINATION}'."
  fi
fi

if [[ "${#SCRIPT_FAILURES[@]}" != 0 ]]; then
  echo -e "${SCRIPT_FAILED}: Encountered unexpected errors when running the following integration tests:\n\n"
  for SCRIPT_FAILURE in "${SCRIPT_FAILURES[@]}"; do
    echo "    - ${SCRIPT_FAILURE}"
    if [[ ${DESTINATION:-""} != "" ]]; then
      mkdir -p "${DESTINATION}"
      cp -r  "./tmp/${SCRIPT_FAILURE}" "${DESTINATION}/${SCRIPT_FAILURE}"
    fi
  done

  echo -e "\n\n"

  if [[ ${DESTINATION:-""} != "" ]]; then
    echo -e "Log files for failed integration tests were saved to '${DESTINATION}'."
  fi
fi



echo -e "\n\n\n#############################################\n\n\n"
