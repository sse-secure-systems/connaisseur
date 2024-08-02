#!/usr/bin/env bash
set -euo pipefail

workload_test() {
    WOLIST=("CronJob" "DaemonSet" "Deployment" "Job" "Pod" "ReplicaSet" "ReplicationController" "StatefulSet")
    
    update_with_file "workload/install.yaml"
    install "make"
    for wo in "${WOLIST[@]}"; do
        do_workload_test "${wo}"
    done
    uninstall "make"
}

do_workload_test() { # WORKLOAD_KIND
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
        wait_for_resource "${KIND}"
        
        # Check that the workload object is actually ready, see #516
        echo -n "Checking if ${KIND} is ready..."
        if check_resource_ready "${KIND}"; then
            echo -e ${SUCCESS}
        else
            echo -e ${FAILED}
            echo "There are ${NUMBER_UNREADY} ${KIND} objects that aren't in a ready state:"
            echo "${STATUSES}"
            kubectl describe ${KIND} # Get us some debug information
            EXIT="1"
        fi
    fi
}

check_resource_ready() { # WORKLOAD_KIND
    export NUMBER_UNREADY=0
    export STATUSES=""

    KIND=${1}
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
            return 1
        fi

        if [[ ${NUMBER_UNREADY} -eq 0 ]]; then
            return 0
        else
            return 1
        fi
}

wait_for_resource() { # WORKLOAD_KIND
    echo -n "Waiting for resource ${1} to be ready..."
    
    export -f check_resource_ready
    timeout 60 bash -c "while ! check_resource_ready ${1}; do sleep 1; done"

    if [[ $? -eq 0 ]]; then
        echo -e ${SUCCESS}
    else
        echo -e ${FAILED}
    fi
}
