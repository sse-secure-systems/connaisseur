#!/usr/bin/env bash

alerting_test() {
    setup_alerting
    update_with_file "alerting/install.yaml"
    install "make"
    multi_test "alerting/cases.yaml"
    check_alerting_endpoint_calls
    uninstall "make"
    cleanup_alerting
}

check_alerting_endpoint_calls() {
    echo -n "Checking whether alert endpoints have been called successfully..."
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

setup_alerting() {
    if [[ "${GITHUB_ACTIONS-}" == "true" ]]; then
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
    docker network connect ${NETWORK} alerting-endpoint
    export ALERTING_ENDPOINT_IP=$(docker container inspect alerting-endpoint | jq -r --arg network ${NETWORK} '.[].NetworkSettings.Networks[$network].IPAddress')
    echo "Alerting interface spun up at ${ALERTING_ENDPOINT_IP}."
}

search_for_minikube() {
    if [[ "$(docker inspect minikube 2> /dev/null | jq -r .[].State.Status || echo 'container not found')" != "running" ]]; then
        eval $(minikube docker-env -u) || true
        if [[ "$(docker inspect minikube 2> /dev/null | jq -r .[].State.Status || echo 'container not found')" != "running" ]]; then
            echo "Minikube not found."
            return 1
        else
            RESET_DOCKER_ENV="true"
            echo "Minikube found."
            return 0
        fi
    else
        echo "Minikube found."
        return 0
    fi
}

cleanup_alerting() {
    if [[ "${GITHUB_ACTIONS-}" == "true" ]]; then
        return
    fi

    echo "Cleaning up alerting interface..."
    docker stop alerting-endpoint || true
    docker rm alerting-endpoint || true

    if [[ "${RESET_DOCKER_ENV}" == "true" ]]; then
        eval $(minikube docker-env) || true
    fi
}