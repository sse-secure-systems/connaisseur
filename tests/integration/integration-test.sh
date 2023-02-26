#!/usr/bin/env bash
set -euo pipefail

# This script is expected to be called from the root folder of Connaisseur
declare -A DEPLOYMENT_RES=(["VALID"]="0" ["INVALID"]="0")
RED="\033[0;31m"
GREEN="\033[0;32m"
NC="\033[0m"
SUCCESS="${GREEN}SUCCESS${NC}"
FAILED="${RED}FAILED${NC}"
EXIT="0"
WOLIST=("CronJob" "DaemonSet" "Deployment" "Job" "Pod" "ReplicaSet" "ReplicationController" "StatefulSet")
TIMEOUT=30
RETRY=3

## Backup helm/values.yaml
cp helm/values.yaml values.yaml.Backup

## LOAD PUBLIC KEY
COSIGN_PUBLIC_KEY="$(printf -- "${COSIGN_PUBLIC_KEY//<br>/\\n          }")"

## Join ghcr integration yaml
if [[ -n "${IMAGE+x}" && -n "${IMAGEPULLSECRET+x}" ]]; then
  yq '. *+ load("tests/integration/var-img.yaml")' tests/integration/ghcr-values.yaml > ghcr-tmp
  envsubst < ghcr-tmp > ghcr-values
  rm ghcr-tmp
else
  echo "" > ghcr-values
fi

### SINGLE TEST CASE ####################################
single_test() { # ID TXT TYP REF NS MSG RES
  echo -n "[$1] $2"
  i=0 # intialize iterator
  while : ; do
    i=$((i+1))
    if [[ "$3" == "deploy" ]]; then
      kubectl run pod-$1 --image="$4" --namespace="$5" -luse="connaisseur-integration-test" >output.log 2>&1 || true
    elif [[ "$3" == "workload" ]]; then
      envsubst <tests/integration/workload-objects/$4.yaml | kubectl apply -f - >output.log 2>&1 || true
    else
      kubectl apply -f $4 >output.log 2>&1 || true
    fi
    # if the webhook couldn't be called, try again.
    [[ ("$(cat output.log)" =~ "failed calling webhook") && $i -lt $RETRY ]] || break
  done
  if [[ ! "$(cat output.log)" =~ "$6" ]]; then
    echo -e ${FAILED}
    echo "::group::Output"
    cat output.log
    kubectl logs -n connaisseur -lapp.kubernetes.io/instance=connaisseur
    echo "::endgroup::"
    EXIT="1"
  else
    echo -e "${SUCCESS}"
  fi
  rm output.log

  if [[ $7 != "null" ]]; then
    DEPLOYMENT_RES[$7]=$((${DEPLOYMENT_RES[$7]} + 1))
  fi

  # 3 tries on first test, 2 tries on second, 1 try for all subsequential
  RETRY=$((RETRY-1))
}

### MULTI TEST CASE FROM FILE ####################################
multi_test() { # TEST_CASE: key in the `test_cases` dict in the cases.yaml
  # converting to json, as yq processing is pretty slow
  test_cases=$(yq e -o=json ".test_cases.$1" tests/integration/cases.yaml)
  len=$(echo ${test_cases} | jq 'length')
  for i in $(seq 0 $(($len - 1))); do
    test_case=$(echo ${test_cases} | jq ".[$i]")
    ID=$(echo ${test_case} | jq -r ".id")
    TEST_CASE_TXT=$(echo ${test_case} | jq -r ".txt")
    TYPE=$(echo ${test_case} | jq -r ".type")
    REF=$(echo ${test_case} | jq -r ".ref")
    NAMESPACE=$(echo ${test_case} | jq -r ".namespace")
    EXP_MSG=$(echo ${test_case} | jq -r ".expected_msg")
    EXP_RES=$(echo ${test_case} | jq -r ".expected_result")
    single_test "${ID}" "${TEST_CASE_TXT}" "${TYPE}" "${REF}" "${NAMESPACE}" "${EXP_MSG}" "${EXP_RES}"
  done
}

### WORKLOAD TEST ####################################
workload_test() { # WORKLOAD_KIND
  export KIND=$1
  export APIVERSION=$(kubectl api-resources | awk -v KIND=${KIND} '{ if($NF == ""KIND"") print $(NF-2);}')

  # UNSIGNED
  export TAG=unsigned
  echo "::group::${KIND}_${APIVERSION}_${TAG}.yaml"
  envsubst <tests/integration/workload-objects/${KIND}.yaml | cat
  echo "::endgroup::"
  single_test "w_${KIND}_${APIVERSION}_${TAG}" "Testing ${KIND} using ${APIVERSION} and ${TAG} image..." "workload" "${KIND}" "default" "Unable to find signed digest for image docker.io/securesystemsengineering/testimage:unsigned." "null"

  # SIGNED
  export TAG=signed
  echo "::group::${KIND}_${APIVERSION}_${TAG}.yaml"
  envsubst <tests/integration/workload-objects/${KIND}.yaml | cat
  echo "::endgroup::"
  single_test "w_${KIND}_${APIVERSION}_${TAG}" "Testing ${KIND} using ${APIVERSION} and ${TAG} image..." "workload" "${KIND}" "default" " created" "null"

  if [[ "${GITHUB_BASE_REF}" == "master" ]]; then
    # Check that the workload object is actually ready, see #516
    echo -n "Checking readiness of deployed resources..."
    if [[ "${KIND}" == "StatefulSet" ]]; then
      sleep 30 # StatefulSet provisions a PVC, which needs more time. A lot more sometimes...
    fi
    sleep 5

    # Output of different objects differs considerably, in particular in JSON representation
    # To have less to differentiate, we parse the visual representation
    if [[ "${KIND}" == "Pod" || "${KIND}" == "Deployment" || "${KIND}" == "StatefulSet" ]]; then
      # NAME                     READY   UP-TO-DATE   AVAILABLE   AGE
      # coredns                  2/2     2            2           177d
      STATUSES=$(kubectl get ${KIND})
      NUMBER_UNREADY=$(( $(echo "${STATUSES}" | awk '{print $2}' | awk -F "/" '$1!=$2 { print $0 }' | wc -l) - 1)) # Preserving header row for better readability
    elif [[ "${KIND}" == "ReplicaSet" || "${KIND}" == "DaemonSet" || "${KIND}" == "ReplicationController" ]]; then
      # NAME                 DESIRED   CURRENT   READY   AGE
      # coredns-558bd4d5db   2         2         2       177d
      STATUSES=$(kubectl get ${KIND} | awk '$2!=$4 {print $0}')
      NUMBER_UNREADY=$(( $(echo "${STATUSES}" | wc -l) - 1 )) # Preserving header row for better readability
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

### COMPLEXITY TEST ####################################
complexity_test() { #
  echo -n 'Testing Connaisseur with complex requests...'
  kubectl apply -f tests/integration/deployments/complexity.yaml >output.log 2>&1 || true
  if [[ ! ("$(cat output.log)" =~ 'deployment.apps/redis-with-many-instances created' && "$(cat output.log)" =~ 'pod/pod-with-many-containers created' && "$(cat output.log)" =~ 'pod/pod-with-many-containers-and-init-containers created' && "$(cat output.log)" =~ 'pod/pod-with-some-containers-and-init-containers created' && "$(cat output.log)" =~ 'pod/pod-with-coinciding-containers-and-init-containers created') ]]; then
    echo -e ${FAILED}
    echo "::group::Output"
    cat output.log
    echo "::endgroup::"
    EXIT="1"
  else
    echo -e "${SUCCESS}"
  fi
  rm output.log
}

### LOAD TEST ####################################
load_test() { #
  NUMBER_OF_INSTANCES=100
  echo -n 'Testing Connaisseur with many requests...'
  parallel --jobs 20 ./tests/integration/cause_load.sh {1} :::: <(seq ${NUMBER_OF_INSTANCES}) >output.log 2>&1 || true
  NUMBER_CREATED=$(cat output.log | grep "deployment[.]apps/redis-[0-9]* created" | wc -l || echo "0")
  if [[ ${NUMBER_CREATED} != "${NUMBER_OF_INSTANCES}" ]]; then
    echo -e ${FAILED}
    echo "::group::Output"
    echo "Only ${NUMBER_CREATED}/${NUMBER_OF_INSTANCES} pods were created."
    cat output.log
    echo "::endgroup::"
    EXIT="1"
  else
    echo -e "${SUCCESS}"
  fi
  rm output.log
}

### CREATE IMAGEPULLSECRET ####################################
create_imagepullsecret_in_ns() { # NAMESPACE # CREATE
  local CREATE=${2:-true}
  if $CREATE; then
    echo -n "Creating Namespace '${1}'..."
    kubectl create ns ${1} >/dev/null || {
      echo -e "${FAILED}"
      exit 1
    }
    echo -e "${SUCCESS}"
  fi
  if [[ -n "${IMAGEPULLSECRET+x}" ]]; then
    echo -n "Creating imagePullSecret '${IMAGEPULLSECRET}'..."
    kubectl create secret generic ${IMAGEPULLSECRET} \
      --from-file=.dockerconfigjson=$HOME/.docker/config.json \
      --type=kubernetes.io/dockerconfigjson \
      --namespace=${1} >/dev/null || {
      echo -e "${FAILED}"
      exit 1
    }
    echo -e "${SUCCESS}"
  fi
}

### INSTALLING CONNAISSEUR ####################################
make_install() {
  create_imagepullsecret_in_ns "connaisseur"
  echo -n "Installing Connaisseur..."
  make install >/dev/null || {
    echo -e "${FAILED}"
    exit 1
  }
  echo -e "${SUCCESS}"
  sleep ${TIMEOUT}
}

helm_install_namespace() { # NAMESPACE
  create_imagepullsecret_in_ns ${1}
  echo -n "Installing Connaisseur in namespace ${1}..."
  helm install connaisseur helm --atomic --create-namespace \
    --namespace ${1} >/dev/null || {
    echo -e "${FAILED}"
    exit 1
  }
  echo -e "${SUCCESS}"
  sleep ${TIMEOUT}
}

helm_install_namespace_no_create() { # NAMESPACE
  create_imagepullsecret_in_ns ${1} false
  echo -n "Installing Connaisseur in namespace ${1}..."
  helm install connaisseur helm --atomic \
    --namespace ${1} >/dev/null || {
    echo -e "${FAILED}"
    exit 1
  }
  echo -e "${SUCCESS}"
  sleep ${TIMEOUT}
}

helm_install() {
  helm_install_namespace "connaisseur"
}

helm_repo_install() {
  # will install unconfigured Connaisseur
  echo -n "Installing Connaisseur..."
  helm repo add connaisseur https://sse-secure-systems.github.io/connaisseur/charts >/dev/null
  helm install connaisseur connaisseur/connaisseur --atomic --create-namespace \
    --namespace connaisseur >/dev/null || {
    echo -e "${FAILED}"
    exit 1
  }
  echo -e "${SUCCESS}"
  sleep ${TIMEOUT}
}

### UPGRADING CONNAISSEUR ####################################
make_upgrade() {
  echo -n 'Upgrading Connaisseur...'
  make upgrade >/dev/null || {
    echo -e ${FAILED}
    exit 1
  }
  echo -e "${SUCCESS}"
}

helm_upgrade_namespace() { # NS
  echo -n 'Upgrading Connaisseur...'
  helm upgrade connaisseur helm -n ${1} --wait >/dev/null || {
    echo -e ${FAILED}
    exit 1
  }
  echo -e "${SUCCESS}"
}

### UNINSTALLING CONNAISSEUR ####################################
make_uninstall() {
  echo -n 'Uninstalling Connaisseur...'
  make uninstall >/dev/null || {
    echo -e "${FAILED}"
    exit 1
  }
  echo -e "${SUCCESS}"
}

helm_uninstall() {
  echo -n 'Uninstalling Connaisseur...'
  helm uninstall connaisseur -n connaisseur >/dev/null &&
    kubectl delete ns connaisseur >/dev/null || {
    echo -e "${FAILED}"
    exit 1
  }
  echo -e "${SUCCESS}"
}

update_values() { # [EXPRESSION...]
  for update in "$@"; do
    yq e -i "${update}" helm/values.yaml
  done
}

update_values_minimal() {
  yq '. *+ load("ghcr-values")' -i helm/values.yaml
}

update_via_env_vars() {
  envsubst < tests/integration/update.yaml > update
  yq '. *+ load("ghcr-values")' -i update
  yq eval-all --inplace 'select(fileIndex == 0) * select(fileIndex == 1)' helm/values.yaml update
  rm update
}

update_helm_for_workloads() {
  envsubst < tests/integration/update-for-workloads.yaml > update
  yq '. *+ load("ghcr-values")' -i update
  yq eval-all --inplace 'select(fileIndex == 0) * select(fileIndex == 1)' helm/values.yaml update
  rm update
}

debug_vaules() {
  echo "::group::values.yaml"
  cat helm/values.yaml
  echo "::endgroup::"
}

### RUN REGULAR INTEGRATION TEST ####################################
regular_int_test() {
  multi_test "regular"

  ### EDGE CASE TAG IN RELEASES AND TARGETS ####################################
  echo -n "[edge1] Testing edge case of tag defined in both targets and release json file..."
  DEPLOYED_SHA=$(kubectl get pod pod-rs -o yaml | yq e '.spec.containers[0].image' - | sed 's/.*sha256://')
  if [[ "${DEPLOYED_SHA}" != 'c5327b291d702719a26c6cf8cc93f72e7902df46547106a9930feda2c002a4a7' ]]; then
    echo -e "${FAILED}"
    EXIT="1"
  else
    echo -e "${SUCCESS}"
  fi

  ### ALERTING TEST ####################################
  echo -n "Checking whether alert endpoints have been called successfully..."
  ENDPOINT_HITS="$(curl -s ${ALERTING_ENDPOINT_IP}:56243 --header 'Content-Type: application/json')"
  NUMBER_OF_DEPLOYMENTS=$((${DEPLOYMENT_RES["VALID"]} + ${DEPLOYMENT_RES["INVALID"]}))
  EXPECTED_ENDPOINT_HITS=$(jq -n \
    --argjson REQUESTS_TO_SLACK_ENDPOINT ${NUMBER_OF_DEPLOYMENTS} \
    --argjson REQUESTS_TO_OPSGENIE_ENDPOINT ${DEPLOYMENT_RES["VALID"]} \
    --argjson REQUESTS_TO_KEYBASE_ENDPOINT ${DEPLOYMENT_RES["INVALID"]} \
    '{
  "successful_requests_to_slack_endpoint":$REQUESTS_TO_SLACK_ENDPOINT,
  "successful_requests_to_opsgenie_endpoint": $REQUESTS_TO_OPSGENIE_ENDPOINT,
  "successful_requests_to_keybase_endpoint": $REQUESTS_TO_KEYBASE_ENDPOINT
  }')
  diff <(echo "$ENDPOINT_HITS" | jq -S .) <(echo "$EXPECTED_ENDPOINT_HITS" | jq -S .) >diff.log 2>&1 || true
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

### COSIGN TEST ####################################
cosign_int_test() {
  multi_test "cosign"
}

### MULTI-COSIGNed TEST ####################################
multi-cosigned_int_test() {
  multi_test "multi-cosigned"
}

### REKOR-COSIGNed TEST ####################################
rekor-cosigned_int_test() {
  multi_test "rekor-cosigned"
}

### NAMESPACE VALIDATION TEST ####################################
namespace_val_int_test() {
  echo -n "Creating namespaces..."
  kubectl create namespace ignoredns >/dev/null
  kubectl label ns ignoredns securesystemsengineering.connaisseur/webhook=ignore use=connaisseur-integration-test >/dev/null
  kubectl create namespace validatedns >/dev/null
  kubectl label ns validatedns securesystemsengineering.connaisseur/webhook=validate use=connaisseur-integration-test >/dev/null
  echo -e "${SUCCESS}"

  multi_test "ignore-namespace-val"
  update_values '.namespacedValidation.mode="validate"'
  make_upgrade # upgrade Connaisseur installation
  multi_test "validate-namespace-val"
}

### DEPLOYMENT TEST ####################################
deployment_int_test() {
  multi_test "deployment"
}

### PRECONFIG TEST ####################################
pre_config_int_test() {
  multi_test "pre-config"
}

### CERTIFICATE INT TEST ####################################
certificate_int_test() {
  multi_test "certificate"
}

### CERTIFICATE TEST ####################################
certificate_check() {
  DIFF=$(diff tests/integration/tls.key <(kubectl get secrets -n connaisseur connaisseur-tls -o json | jq -r '.data."tls.key"' | base64 -d) || true)
  if [[ ${DIFF} != "" ]]; then
    echo "Unexpected TLS key. Should be pre-configured one."
    EXIT=1
  else
    echo "Found expected TLS key."
  fi
  DIFF=$(diff tests/integration/tls.cert <(kubectl get secrets -n connaisseur connaisseur-tls -o json | jq -r '.data."tls.crt"' | base64 -d) || true)
  if [[ ${DIFF} != "" ]]; then
    echo "Unexpected TLS certificate. Should be pre-configured one."
    EXIT=1
  else
    echo "Found expected TLS certificate."
  fi
}

case $1 in
"regular")
  update_via_env_vars
  make_install
  regular_int_test
  make_uninstall
  ;;
"cosign")
  update_via_env_vars
  make_install
  cosign_int_test
  ;;
"multi-cosigned")
  update_via_env_vars
  make_install
  multi-cosigned_int_test
  ;;
"rekor-cosigned")
  update_via_env_vars
  make_install
  rekor-cosigned_int_test
  ;;
"namespace-val")
  update_via_env_vars
  update_values '.namespacedValidation.enabled=true'
  make_install
  namespace_val_int_test
  ;;
"other-ns")
  echo "Testing deployment of Connaisseur in a different namespace than the default. See e.g. https://github.com/sse-secure-systems/connaisseur/issues/724"
  update_via_env_vars
  CLUSTER_NAME=$(kubectl config get-contexts $(kubectl config current-context) --no-headers | awk '{print $3}')
  CTX=deployconnaisseur
  NAME=securityadmin
  NS=security

  kubectl create ns ${NS}
  # Create service account with all permission on one namespace and some other, but non on other namespaces
  kubectl create serviceaccount ${NAME} --namespace=${NS}
  kubectl create rolebinding ${NAME} --clusterrole=cluster-admin --serviceaccount=${NS}:${NAME} --namespace=${NS}
  kubectl create clusterrole auxillary --verb='*' --resource=clusterrole,clusterrolebinding,mutatingwebhookconfigurations
  kubectl create clusterrolebinding ${NAME} --clusterrole=auxillary --serviceaccount=${NS}:${NAME}

  # Use that service account's config to run the Connaisseur deployment to see no other namespace is touched
  TOKEN=$(kubectl create token ${NAME} --namespace=${NS})
  kubectl config set-credentials ${CTX} --token=${TOKEN}
  kubectl config set-context ${CTX} --cluster=${CLUSTER_NAME} --user=${CTX}
  kubectl config use-context ${CTX}
  helm_install_namespace_no_create ${NS}
  single_test "on" "Testing unsigned image..." "deploy" "securesystemsengineering/testimage:unsigned" "${NS}" "Unable to find signed digest for image docker.io/securesystemsengineering/testimage:unsigned." "INVALID"
  ;;
"deployment")
  update_via_env_vars
  update_values '.policy += {"pattern": "docker.io/library/*:*", "validator": "dockerhub-basics", "with": {"trust_root": "docker-official"}}'
  make_install
  deployment_int_test
  ;;
"pre-config")
  update_values_minimal
  helm_install
  pre_config_int_test
  helm_uninstall
  ;;
"pre-and-workload")
  update_helm_for_workloads
  make_install
  pre_config_int_test
  for wo in "${WOLIST[@]}"; do
    workload_test "${wo}"
  done
  ;;
"helm-repo")
  helm_repo_install
  pre_config_int_test
  ;;
"complexity")
  update_values_minimal
  update_values '.deployment.replicasCount=3' '.deployment.resources= {"limits": {"cpu":"1000m", "memory":"512Mi"},"requests": {"cpu":"500m", "memory":"512Mi"}}'
  make_install
  complexity_test
  ;;
"load")
  update_values_minimal
  make_install
  load_test
  ;;
"configured-cert")
  echo "Testing deployment of Connaisseur using a pre-configured TLS certificate. See issue https://github.com/sse-secure-systems/connaisseur/issues/225"
  update_via_env_vars
  make_install
  certificate_int_test
  # Clean up such that next test doesn't run into existing test pods
  kubectl delete pods -luse="connaisseur-integration-test" -A >/dev/null
  yq eval-all --inplace 'select(fileIndex == 0) * select(fileIndex == 1)' helm/values.yaml tests/integration/update-cert.yaml
  make_upgrade
  certificate_check
  certificate_int_test
  ;;
*)
  echo "Invalid test case. Exiting..."
  exit 1
  ;;
esac

if [[ "${EXIT}" != "0" ]]; then
  echo -e "${FAILED} Failed integration test."
else
  echo -e "${SUCCESS} Passed integration test."
fi

if [[ "${GITHUB_ACTIONS-}" == "true" ]]; then
  exit $((${EXIT}))
fi

echo 'Cleaning up installation and test resources...'
make uninstall >/dev/null 2>&1 || true
kubectl delete all,cronjobs,daemonsets,jobs,replicationcontrollers,statefulsets,namespaces -luse="connaisseur-integration-test" -A >/dev/null
mv values.yaml.backup helm/values.yaml
echo 'Finished cleanup.'
