#! /bin/bash
set -euo pipefail

# This script is expected to be called from the root folder of Connaisseur
# This script executes a stress test and a load test on a Connaisseur deployment
# Stress test consists of a moderately complex set of requests
# Load test consists of a lot of identical requests

NUMBER_OF_INSTANCES=100

echo 'Preparing Connaisseur config...'
yq eval-all --inplace 'select(fileIndex == 0) * select(fileIndex == 1)' helm/values.yaml tests/integration/load-update.yaml
echo 'Config set'

echo 'Installing Connaisseur...'
helm install connaisseur helm --atomic --create-namespace --namespace connaisseur || { echo 'Failed to install Connaisseur'; exit 1; }
echo 'Successfully installed Connaisseur'

echo 'Testing Connaisseur with complex requests...'
kubectl apply -f tests/integration/stresstest.yaml >output.log 2>&1 || true

if [[ ! ("$(cat output.log)" =~ 'deployment.apps/redis-with-many-instances created' && "$(cat output.log)" =~ 'pod/pod-with-many-containers created' && "$(cat output.log)" =~ 'pod/pod-with-many-containers-and-init-containers created' && "$(cat output.log)" =~ 'pod/pod-with-some-containers-and-init-containers created' && "$(cat output.log)" =~ 'pod/pod-with-coinciding-containers-and-init-containers created') ]]; then
  echo 'Failed test with complex requests. Output:'
  cat output.log
  exit 1
else
  echo 'Successfully passed test with complex requests'
fi

echo 'Cleaning up before second test'
kubectl delete all -ltest=stresstest

echo 'Testing Connaisseur with many requests...'
parallel --jobs 20 ./tests/integration/cause_load.sh {1} :::: <(seq ${NUMBER_OF_INSTANCES}) >output.log 2>&1 || true

NUMBER_CREATED=$(cat output.log | grep "deployment[.]apps/redis-[0-9]* created" | wc -l || echo "0")
if [[ ${NUMBER_CREATED} != "${NUMBER_OF_INSTANCES}" ]]; then
  echo "Failed load test. Only ${NUMBER_CREATED}/${NUMBER_OF_INSTANCES} pods were created"
  exit 1
else
  echo "Successfully passed load test"
fi

# Cleanup can be skipped in GitHub Actions, since uninstall is already tested in other integration test
if [[ "${GITHUB_ACTIONS-}" == "true" ]]; then
  exit 0
fi

echo 'Cleaning up'
kubectl delete all -ltest=loadtest

echo 'Uninstalling Connaisseur...'
helm uninstall connaisseur --namespace connaisseur || { echo 'Failed to uninstall Connaisseur'; exit 1; }
echo 'Successfully uninstalled Connaisseur'

rm output.log
echo 'Passed load test'
