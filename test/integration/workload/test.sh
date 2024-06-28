#!/usr/bin/env bash
set -euo pipefail

pre_workload_test() {
    WOLIST=("CronJob" "DaemonSet" "Deployment" "Job" "Pod" "ReplicaSet" "ReplicationController" "StatefulSet")
    
    install "make"
    multi_test "pre-config/cases.yaml"
    for wo in "${WOLIST[@]}"; do
        workload_test "${wo}"
    done
    uninstall "make"
}

workload_test() { # WORKLOAD_KIND
    export KIND=$1
    export APIVERSION=$(kubectl api-resources | awk -v KIND=${KIND} '{ if($NF == ""KIND"") print $(NF-2);}')

    # UNSIGNED
    export TAG=unsigned
    echo "::group::${KIND}_${APIVERSION}_${TAG}.yaml"
    envsubst <test/integration/workload/${KIND}.yaml | cat
    echo "::endgroup::"
    single_test "w_${KIND}_${APIVERSION}_${TAG}" "Testing ${KIND} using ${APIVERSION} and ${TAG} image..." "workload" "${KIND}" "default" "no tag 'unsigned' found in targets" "null"

    # SIGNED
    export TAG=signed
    echo "::group::${KIND}_${APIVERSION}_${TAG}.yaml"
    envsubst <test/integration/workload/${KIND}.yaml | cat
    echo "::endgroup::"
    single_test "w_${KIND}_${APIVERSION}_${TAG}" "Testing ${KIND} using ${APIVERSION} and ${TAG} image..." "workload" "${KIND}" "default" " created" "null"

    if [[ "${GITHUB_BASE_REF:-"no-github-base-ref-set"}" == "master" || "${GITHUB_BASE_REF:-"no-github-base-ref-set"}" == "no-github-base-ref-set" ]]; then
        # Check that the workload object is actually ready, see #516
        echo -n "Checking readiness of deployed resources..."
        if [[ "${KIND}" == "StatefulSet" ]]; then
            sleep 30 # StatefulSet provisions a PVC, which needs more time. A lot more sometimes...
        fi
        if [[ "${CI-}" == "true" ]]; then
            SLEEP_TIME=5
        else
            SLEEP_TIME=20
        fi
        sleep ${SLEEP_TIME}

        # Output of different objects differs considerably, in particular in JSON representation
        # To have less to differentiate, we parse the visual representation
        if [[ "${KIND}" == "Pod" || "${KIND}" == "Deployment" || "${KIND}" == "StatefulSet" ]]; then
            # NAME                     READY   UP-TO-DATE   AVAILABLE   AGE
            # coredns                  2/2     2            2           177d
            STATUSES=$(kubectl get ${KIND})
            NUMBER_UNREADY=$(($(echo "${STATUSES}" | awk '{print $2}' | awk -F "/" '$1!=$2 { print $0 }' | wc -l) - 1)) # Preserving header row for better readability
        elif [[ "${KIND}" == "ReplicaSet" || "${KIND}" == "DaemonSet" || "${KIND}" == "ReplicationController" ]]; then
            # NAME                 DESIRED   CURRENT   READY   AGE
            # coredns-558bd4d5db   2         2         2       177d
            STATUSES=$(kubectl get ${KIND} | awk '$2!=$4 {print $0}')
            NUMBER_UNREADY=$(($(echo "${STATUSES}" | wc -l) - 1)) # Preserving header row for better readability
        elif [[ "${KIND}" == "Job" || "${KIND}" == "CronJob" ]]; then
            # NAME                        COMPLETIONS   DURATION   AGE
            # cronjob-signed-1674474300   0/1           30s        30s
            # job-signed                  0/1           10s        10s
            NUMBER_UNREADY=0
            # Logic doesn't really work for Jobs
        else
            echo -e ${FAILED}
            echo "New workload object of type ${KIND} encountered. Add logic to parse whether it is ready."
            EXIT="1"
        fi

        if [[ ${NUMBER_UNREADY} -ne 0 ]]; then
            echo -e ${FAILED}
            echo "There are ${NUMBER_UNREADY} ${KIND} objects that aren't in a ready state:"
            echo "${STATUSES}"
            kubectl describe ${KIND} # Get us some debug information
            EXIT="1"
        else
            echo -e ${SUCCESS}
        fi
    fi
}
