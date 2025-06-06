#!/usr/bin/env bash
set -euo pipefail

alerting_test() {
    setup_alerting
    update_with_file "alerting/install.yaml"
    install "make"
    multi_test "alerting/cases.yaml"
    check_alerting_endpoint_calls
    uninstall "make"
    cleanup_alerting
}

setup_alerting() {
    # skip if running in CI
    if [[ "${CI-}" == "true" ]]; then
        return
    fi

    if search_for_minikube; then
        # minikube
        NETWORK=$(docker container inspect minikube | jq -r '.[].NetworkSettings.Networks | to_entries | .[].key')
        echo "Found minikube network: ${NETWORK}"
    else
        # kind
        NETWORK=$(docker container inspect kind-control-plane | jq -r '.[].NetworkSettings.Networks | to_entries | .[].key')
        echo "Found kind network: ${NETWORK}"
    fi

    if [[ -z "${NETWORK}" ]]; then
        echo "Failed to find network for alerting endpoint."
        exit 1
    fi

    echo "Spinning up alerting interface..."
    docker run -d --name alerting-endpoint -p 56243:56243 docker.io/securesystemsengineering/alerting-endpoint:latest > /dev/null
    docker network connect "${NETWORK}" alerting-endpoint
    export ALERTING_ENDPOINT_IP=$(docker container inspect alerting-endpoint | jq -r --arg network "${NETWORK}" '.[].NetworkSettings.Networks[$network].IPAddress')
    echo "Alerting interface spun up at ${ALERTING_ENDPOINT_IP}."
}

check_alerting_endpoint_calls() {
    echo -n "Checking whether alert endpoints have been called successfully..."
    if [[ "${CI-}" == "true" ]]; then
        # make alerting service reachable from here (outside k3s), so test instrumentation can access endpoint
        kubectl port-forward services/alerting-service 56243:56243 &
        sleep 2 # allow forwarding to start
        export ALERTING_ENDPOINT_IP=localhost # due to port-forwarding the service is now available locally
    fi
    ENDPOINT_HITS="$(curl -s ${ALERTING_ENDPOINT_IP}:56243 --header 'Content-Type: application/json' || echo '{"msg": "Failed to retrieve alert endpoint hits"}')"
    NUMBER_OF_DEPLOYMENTS=$((${DEPLOYMENT_RES["ADMIT"]} + ${DEPLOYMENT_RES["REJECT"]}))
    EXPECTED_ENDPOINT_HITS=$(jq -n \
        --argjson REQUESTS_TO_SLACK_ENDPOINT ${NUMBER_OF_DEPLOYMENTS} \
        --argjson REQUESTS_TO_OPSGENIE_ENDPOINT ${DEPLOYMENT_RES["ADMIT"]} \
        --argjson REQUESTS_TO_KEYBASE_ENDPOINT ${DEPLOYMENT_RES["REJECT"]} \
        '{
  "successful_requests_to_slack_endpoint": $REQUESTS_TO_SLACK_ENDPOINT,
  "successful_requests_to_opsgenie_endpoint": $REQUESTS_TO_OPSGENIE_ENDPOINT,
  "successful_requests_to_keybase_endpoint": $REQUESTS_TO_KEYBASE_ENDPOINT
  }')
    diff <(echo "${ENDPOINT_HITS}" | jq -S .) <(echo "${EXPECTED_ENDPOINT_HITS}" | jq -S .) >diff.log 2>&1 || true
    if [[ -s diff.log ]]; then
        echo -e "${FAILED}"
        echo "::group::Alerting endpoint diff:"
        cat diff.log
        echo "::endgroup::"
        EXIT="1"
    else
        echo -e "${SUCCESS}"
    fi
    rm diff.log
}

cleanup_alerting() {
    # skip if running in CI
    if [[ "${CI-}" == "true" ]]; then
        return
    fi

    echo "Cleaning up alerting interface..."
    docker stop alerting-endpoint || true
    docker rm alerting-endpoint || true

    # reset docker-env if it was changed
    if [[ "${RESET_DOCKER_ENV-}" == "true" ]]; then
        eval $(minikube docker-env) || true
    fi
}
