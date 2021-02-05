#! /bin/bash
set -euo pipefail

# This script is expected to be called from the root folder of Connaisseur
declare -i NUMBER_OF_VALID_DEPLOYMENTS=0
declare -i NUMBER_OF_INVALID_DEPLOYMENTS=0

echo 'Preparing Connaisseur config...'
envsubst < connaisseur/tests/integration/update.yaml > update
yq eval-all --inplace 'select(fileIndex == 0) * select(fileIndex == 1)' helm/values.yaml update
rm update
echo 'Config set'

echo 'Installing Connaisseur...'
make install || { echo 'Failed to install Connaisseur'; exit 1; }
echo 'Successfully installed Connaisseur'

echo 'Testing unsigned image...'
kubectl run pod --image=securesystemsengineering/testimage:unsigned >output.log 2>&1 || true
NUMBER_OF_INVALID_DEPLOYMENTS+=1

if [[ "$(cat output.log)" != 'Error from server: admission webhook "connaisseur-svc.connaisseur.svc" denied the request: could not find signed digest for image "docker.io/securesystemsengineering/testimage:unsigned" in trust data.' ]]; then
  echo 'Failed to deny unsigned image or failed with unexpected error. Output:'
  cat output.log
  exit 1
else
  echo 'Successfully denied usage of unsigned image'
fi

echo 'Testing image signed under different key...'
kubectl run pod --image=library/redis >output.log 2>&1 || true
NUMBER_OF_INVALID_DEPLOYMENTS+=1

if [[ "$(cat output.log)" != 'Error from server: admission webhook "connaisseur-svc.connaisseur.svc" denied the request: failed to verify signature of trust data.' ]]; then
  echo 'Failed to deny image signed with different key or failed with unexpected error. Output:'
  cat output.log
  exit 1
else
  echo 'Successfully denied usage of image signed under different key'
fi

echo 'Testing signed image...'
kubectl run pod --image=securesystemsengineering/testimage:signed >output.log 2>&1 || true
NUMBER_OF_VALID_DEPLOYMENTS+=1

if [[ "$(cat output.log)" != 'pod/pod created' ]]; then
  echo 'Failed to allow signed image. Output:'
  cat output.log
  exit 1
else
  echo 'Successfully allowed usage of signed image'
fi

echo 'Testing deployment of unsigned init container along with a valid container...'
kubectl apply -f connaisseur/tests/integration/valid_container_with_unsigned_init_container_image.yml >output.log 2>&1 || true
NUMBER_OF_INVALID_DEPLOYMENTS+=1

if [[ "$(cat output.log)" != 'Error from server: error when creating "connaisseur/tests/integration/valid_container_with_unsigned_init_container_image.yml": admission webhook "connaisseur-svc.connaisseur.svc" denied the request: could not find signed digest for image "docker.io/securesystemsengineering/testimage:unsigned" in trust data.' ]]; then
  echo 'Allowed an unsigned image via init container or failed due to an unexpected error handling init containers. Output:'
  cat output.log
  exit 1
else
  echo 'Successfully denied unsigned image in init container'
fi

echo 'Checking whether alert endpoints have been called successfully'
ENDPOINT_HITS=$(curl 0.0.0.0:56243 --header "Content-Type: application/json")
let NUMBER_OF_DEPLOYMENTS=${NUMBER_OF_INVALID_DEPLOYMENTS}+${NUMBER_OF_VALID_DEPLOYMENTS}
EXPECTED_ENDPOINT_HITS=$(jq -n \
--argjson REQUESTS_TO_SLACK_ENDPOINT ${NUMBER_OF_DEPLOYMENTS} \
--argjson REQUESTS_TO_OPSGENIE_ENDPOINT  ${NUMBER_OF_VALID_DEPLOYMENTS} \
--argjson REQUESTS_TO_KEYBASE_ENDPOINT ${NUMBER_OF_VALID_DEPLOYMENTS} \
'{
"successful_requests_to_slack_endpoint":$REQUESTS_TO_SLACK_ENDPOINT,
"successful_requests_to_opsgenie_endpoint": $REQUESTS_TO_OPSGENIE_ENDPOINT,
"successful_requests_to_keybase_endpoint": $REQUESTS_TO_KEYBASE_ENDPOINT
}')
diff <(echo $ENDPOINT_HITS | jq -S .) <(echo $EXPECTED_ENDPOINT_HITS | jq -S .) >output.log 2>&1
if [[ "$(cat output.log)" != "" ]]; then
  cat output.log
  exit 1
else
  echo 'Successfully called mocked alert endpoints'
fi

echo 'Uninstalling Connaisseur...'
make uninstall || { echo 'Failed to uninstall Connaisseur'; exit 1; }
echo 'Successfully uninstalled Connaisseur'

rm output.log
echo 'Passed integration test'
