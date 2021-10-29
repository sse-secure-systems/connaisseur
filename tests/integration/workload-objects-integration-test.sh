#!/usr/bin/env bash
set -euo pipefail

# This script is expected to be called from the root folder of Connaisseur

# List of Workload Objects
woList=("CronJob" "DaemonSet" "Deployment" "Job" "Pod" "ReplicaSet" "ReplicationController" "StatefulSet")

echo '** Prepare Connaisseur config'
yq eval-all --inplace 'select(fileIndex == 0) * select(fileIndex == 1)' helm/values.yaml tests/integration/preconfig-update.yaml
echo '>> Config set'

echo -e '\n** Install Connaisseur'
helm install connaisseur helm --atomic --create-namespace --namespace connaisseur || { echo '>> Failed to install Connaisseur'; exit 1; }
echo '>> Successfully installed Connaisseur'

for wo in "${woList[@]}"; do
    export KIND=${wo}
    echo -e "\n##################################\n** Kubernetes Resource: ${KIND}"

    export APIVERSION=$(kubectl api-resources | awk -v KIND=${KIND} '{ if($NF == ""KIND"") print $(NF-2);}')
    echo "** API Version: ${APIVERSION}"

    # UNSIGNED
    export TAG=unsigned

    echo -e "\n** Render '${KIND}' using '${APIVERSION}' and '${TAG}' image"
    envsubst < tests/integration/workload-objects/${KIND}.yaml | cat

    echo -e "\n** Deploy '${KIND}' using '${APIVERSION}' and '${TAG}' image"
    envsubst < tests/integration/workload-objects/${KIND}.yaml | kubectl apply -f - >output.log 2>&1 || true

    if [[ ! "$(cat output.log)" =~ 'Unable to find signed digest for image docker.io/securesystemsengineering/testimage:unsigned.' ]]; then
      echo '>> Failed to deny unsigned image or failed with unexpected error. Output:'
      cat output.log
      exit 1
    else
      echo '>> Successfully denied usage of unsigned image'
    fi

    # SIGNED
    export TAG=signed

    echo -e "\n** Render '${KIND}' using '${APIVERSION}' and '${TAG}' image"
    envsubst < tests/integration/workload-objects/${KIND}.yaml | cat

    echo -e "\n** Deploy '${KIND}' using '${APIVERSION}' and '${TAG}' image"
    envsubst < tests/integration/workload-objects/${KIND}.yaml | kubectl apply -f - >output.log 2>&1 || true

    if [[ ! "$(cat output.log)" =~ ' created' ]]; then
      echo '>> Failed to allow signed image. Output:'
      cat output.log
      exit 1
    else
      cat output.log
      echo '>> Successfully allowed usage of signed image'
    fi

    echo -e "\n** Delete '${KIND}' using '${APIVERSION}' and '${TAG}' image"
    envsubst < tests/integration/workload-objects/${KIND}.yaml | kubectl delete -f - || true

done

echo -e '\n** Uninstall Connaisseur'
helm uninstall connaisseur --namespace connaisseur || { echo 'Failed to uninstall Connaisseur'; exit 1; }
echo '>> Successfully uninstalled Connaisseur'

rm output.log
echo -e '\n##################################\n** Passed workload objects integration test'
