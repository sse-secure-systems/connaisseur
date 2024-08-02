#!/usr/bin/env bash
set -euo pipefail

SCRIPT_PATH=$(tmp=$(realpath "$0") && dirname "${tmp}")
EXIT="0"
IT_RUNNING="false"

# install/uninstall/upgrade, utility stuff
source "${SCRIPT_PATH}"/common_functions.sh
# cleanup functions
source "${SCRIPT_PATH}"/cleanup.sh

# backup values.yaml
cp charts/connaisseur/values.yaml charts/connaisseur/values.yaml.bak

# cleanup on exit if not running in CI
if [[ "${CI-}" != "true" && "${NO_TRAP-}" != "true" ]]; then
    trap_add "preserve_and_cleanup" SIGINT SIGTERM EXIT
fi

# update values.yaml with GHCR image
if ghcr_case; then
    ghcr_update "charts/connaisseur/values.yaml"
fi

IT_RUNNING="true"

case ${1:-} in
"regular")
    # testing basic functionality of all validators
    test_case "regular/install.yaml" "regular/cases.yaml" "make" "force"
    ;;
"notaryv1")
    # testing notaryv1 validator
    test_case "notaryv1/install.yaml" "notaryv1/cases.yaml" "make"
    ;;
"cosign")
    # testing cosign validator
    test_case "cosign/install.yaml" "cosign/cases.yaml" "make"
    ;;
"load")
    # testing load
    source "${SCRIPT_PATH}"/load/test.sh
    load_test
    ;;
"namespaced")
    # testing namespace validation feature
    source "${SCRIPT_PATH}"/namespaced/test.sh
    namespaced_validation_test
    ;;
"complexity")
    # testing complex deployments and pods
    # with multiple containers
    source "${SCRIPT_PATH}"/complexity/test.sh
    complexity_test
    ;;
"deployment")
    # testing different deployments with containers
    # and init containers
    test_case "deployment/install.yaml" "deployment/cases.yaml" "make"
    ;;
"pre-config")
    # testing pre-configured values.yaml, without
    # any changes, on deployments
    install "make"
    multi_test "pre-config/cases.yaml"
    uninstall "make"
    ;;
"workload")
    # testing on all workloads
    # and different API versions
    source "${SCRIPT_PATH}"/workload/test.sh
    workload_test
    ;;
"cert")
    # testing a custom TLS certificate 
    # for connaisseur
    source "${SCRIPT_PATH}"/cert/test.sh
    cert_test
;;
"redis-cert")
    # testing a custom TLS certificate
    # for redis
    source "${SCRIPT_PATH}"/redis-cert/test.sh
    redis_cert_test
;;
"upgrade")
    # testing upgradability of connaisseur
    install "release"
    multi_test "pre-config/cases.yaml"
    upgrade "helm"
    multi_test "pre-config/cases.yaml"
;;
"alerting")
    # testing alerting feature
    source "${SCRIPT_PATH}"/alerting/test.sh
    alerting_test
;;
"other-ns")
    # testing whether connaisseur works in other namespaces
    source "${SCRIPT_PATH}"/other-ns/test.sh
    other_ns_test
;;
"self-hosted-notary")
    # testing self-hosted notary
    source "${SCRIPT_PATH}"/self-hosted-notary/test.sh
    self_hosted_notary_test
;;
"all")
    # running all test cases (except load test)
    TESTS=("regular" "notaryv1" "cosign" "namespaced" "complexity" "deployment" "pre-config" "workload" "cert" "redis-cert" "upgrade" "alerting" "other-ns" "self-hosted-notary")

    FAILED_TESTS=()

    for test in "${TESTS[@]}"; do
        echo "--- Running test case: ${test} ---"
        NO_TRAP=true bash "${SCRIPT_PATH}"/main.sh "${test}"

        if [[ $? -ne 0 ]]; then
            FAILED_TESTS+=("${test}")
            EXIT="1"
        fi
        cleanup
        echo -e "\n"
    done

    if [[ ${#FAILED_TESTS[@]} -ne 0 ]]; then
        echo -e "${FAILED} Failed test cases: ${FAILED_TESTS[*]}"
    fi
;;
*)
    # help message
    echo "Usage:"
    echo -e "\tbash test/integration/main.sh <test_case>"
    echo
    echo "Available test cases:"
    echo -e "\tregular"
    echo -e "\tnotaryv1"
    echo -e "\tcosign"
    echo -e "\tload"
    echo -e "\tnamespaced"
    echo -e "\tcomplexity"
    echo -e "\tdeployment"
    echo -e "\tpre-config"
    echo -e "\tworkload"
    echo -e "\tcert"
    echo -e "\tredis-cert"
    echo -e "\tupgrade"
    echo -e "\talerting"
    echo -e "\tother-ns"
    echo -e "\tself-hosted-notary"
    echo -e "\tall"

    exit 2
    ;;
esac
IT_RUNNING="false"

if [[ "${EXIT}" != "0" ]]; then
    echo -e "${FAILED} Failed integration test."
else
    echo -e "${SUCCESS} Passed integration test."
fi

if [[ "${CI-}" == "true" ]]; then
    exit $((${EXIT}))
fi
