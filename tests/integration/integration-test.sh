#! /bin/bash
set -euo pipefail

# This script is expected to be called from the root folder of Connaisseur
declare -i NUMBER_OF_VALID_DEPLOYMENTS=0
declare -i NUMBER_OF_INVALID_DEPLOYMENTS=0

echo 'Preparing Connaisseur config...'
envsubst < tests/integration/update.yaml > update
yq eval-all --inplace 'select(fileIndex == 0) * select(fileIndex == 1)' helm/values.yaml update
rm update
echo 'Config set'

echo 'Installing Connaisseur...'
# 'make' is chosen deliberately below to test the Makefile, while other tests use 'helm' directly
make install || { echo 'Failed to install Connaisseur'; exit 1; }
echo 'Successfully installed Connaisseur'

echo 'Testing unsigned image...'
kubectl run pod --image=securesystemsengineering/testimage:unsigned >output.log 2>&1 || true
NUMBER_OF_INVALID_DEPLOYMENTS+=1

if [[ ! "$(cat output.log)" =~ 'Unable to find signed digest for image docker.io/securesystemsengineering/testimage:unsigned.' ]]; then
  echo 'Failed to deny unsigned image or failed with unexpected error. Output:'
  cat output.log
  exit 1
else
  echo 'Successfully denied usage of unsigned image'
fi

echo 'Testing image signed under different key...'
kubectl run pod --image=library/redis >output.log 2>&1 || true
NUMBER_OF_INVALID_DEPLOYMENTS+=1

if [[ ! "$(cat output.log)" =~ 'Failed to verify signature of trust data root.' ]]; then
  echo 'Failed to deny image signed with different key or failed with unexpected error. Output:'
  cat output.log
  exit 1
else
  echo 'Successfully denied usage of image signed under different key'
fi

echo 'Testing signed image...'
kubectl run pod --image=securesystemsengineering/testimage:signed -lapp.kubernetes.io/instance=connaisseur >output.log 2>&1 || true
NUMBER_OF_VALID_DEPLOYMENTS+=1

if [[ "$(cat output.log)" != 'pod/pod created' ]]; then
  echo 'Failed to allow signed image. Output:'
  cat output.log
  exit 1
else
  echo 'Successfully allowed usage of signed image'
fi

echo 'Testing edge case of tag defined in both targets and release json file...'
DEPLOYED_SHA=$(kubectl get pod pod -o yaml | yq e '.spec.containers[0].image' - | sed 's/.*sha256://')
if [[ "${DEPLOYED_SHA}" != 'c5327b291d702719a26c6cf8cc93f72e7902df46547106a9930feda2c002a4a7' ]]; then
  echo "Connaisseur substituted wrong image: ${DEPLOYED_SHA}"
  exit 1
else
  echo 'Connaisseur substituted correct image'
fi

echo 'Testing signed image with designated signer...'
kubectl run pod2 --image=securesystemsengineering/testimage:special_sig -lapp.kubernetes.io/instance=connaisseur >output.log 2>&1 || true
NUMBER_OF_VALID_DEPLOYMENTS+=1

if [[ "$(cat output.log)" != 'pod/pod2 created' ]]; then
  echo 'Failed to allow image signed by designated signer. Output:'
  cat output.log
  exit 1
else
  echo 'Successfully allowed usage of image signed by designated signer'
fi

echo 'Testing image with missing designated signer...'
kubectl run pod3 --image=securesystemsengineering/testimage:wrong_signer >output.log 2>&1 || true
NUMBER_OF_INVALID_DEPLOYMENTS+=1

if [[ ! "$(cat output.log)" =~ 'Not all required delegations have trust data for image docker.io/securesystemsengineering/testimage:wrong_signer.' ]]; then
  echo 'Failed to deny image with missing designated signer or failed with unexpected error. Output:'
  cat output.log
  exit 1
else
  echo 'Successfully denied usage of image with missing designated signer'
fi

echo 'Testing image with differing designated signers...'
kubectl run pod3 --image=securesystemsengineering/testimage:double_sig >output.log 2>&1 || true
NUMBER_OF_INVALID_DEPLOYMENTS+=1

if [[ ! "$(cat output.log)" =~ 'Found multiple signed digests for image docker.io/securesystemsengineering/testimage:double_sig.' ]]; then
  echo 'Failed to deny image with missing designated signer or failed with unexpected error. Output:'
  cat output.log
  exit 1
else
  echo 'Successfully denied usage of image with differing designated signers'
fi

echo 'Testing deployment of unsigned init container along with a valid container...'
kubectl apply -f tests/integration/valid_container_with_unsigned_init_container_image.yml >output.log 2>&1 || true
NUMBER_OF_INVALID_DEPLOYMENTS+=1

if [[ ! "$(cat output.log)" =~ 'Unable to find signed digest for image docker.io/securesystemsengineering/testimage:unsigned.' ]]; then
  echo 'Allowed an unsigned image via init container or failed due to an unexpected error handling init containers. Output:'
  cat output.log
  exit 1
else
  echo 'Successfully denied unsigned image in init container'
fi

echo 'Testing deployment of valid init container along with a valid container...'
kubectl apply -f tests/integration/valid_init_container.yaml >output.log 2>&1 || true
NUMBER_OF_VALID_DEPLOYMENTS+=1

if [[ "$(cat output.log)" != 'pod/connaisseur-integration-test-pod-valid-init created' ]]; then
  echo 'Failed to deploy a valid initContainer along with a valid container. Output:'
  cat output.log
  exit 1
else
  echo 'Successfully allowed valid image in init container and container'
fi

echo 'Checking whether alert endpoints have been called successfully'
ENDPOINT_HITS=$(curl ${ALERTING_ENDPOINT_IP}:56243 --header "Content-Type: application/json")
let NUMBER_OF_DEPLOYMENTS=${NUMBER_OF_INVALID_DEPLOYMENTS}+${NUMBER_OF_VALID_DEPLOYMENTS}
EXPECTED_ENDPOINT_HITS=$(jq -n \
--argjson REQUESTS_TO_SLACK_ENDPOINT ${NUMBER_OF_DEPLOYMENTS} \
--argjson REQUESTS_TO_OPSGENIE_ENDPOINT  ${NUMBER_OF_VALID_DEPLOYMENTS} \
--argjson REQUESTS_TO_KEYBASE_ENDPOINT ${NUMBER_OF_INVALID_DEPLOYMENTS} \
'{
"successful_requests_to_slack_endpoint":$REQUESTS_TO_SLACK_ENDPOINT,
"successful_requests_to_opsgenie_endpoint": $REQUESTS_TO_OPSGENIE_ENDPOINT,
"successful_requests_to_keybase_endpoint": $REQUESTS_TO_KEYBASE_ENDPOINT
}')
echo "Hit the alerting endpoints ${ENDPOINT_HITS} times; expected was ${EXPECTED_ENDPOINT_HITS}."
diff <(echo $ENDPOINT_HITS | jq -S .) <(echo $EXPECTED_ENDPOINT_HITS | jq -S .) >output.log 2>&1
if [[ -s output.log ]]; then
  cat output.log
  exit 1
else
  echo 'Successfully called mocked alert endpoints'
fi

echo 'Creating test namespaces'
kubectl create namespace ignoredns
kubectl label ns ignoredns securesystemsengineering.connaisseur/webhook=ignore
kubectl create namespace validatedns
kubectl label ns validatedns securesystemsengineering.connaisseur/webhook=validate

echo '### Testing "ignore" label ###'

echo 'Upgrading Connaisseur...'
yq eval-all --inplace 'select(fileIndex == 0) * select(fileIndex == 1)' helm/values.yaml tests/integration/namespaced-update.yaml
make upgrade || { echo 'Failed to upgrade Connaisseur'; exit 1; }
echo 'Successfully upgraded Connaisseur'

echo 'Testing unsigned image in unlabelled namespace...'
kubectl run pod --namespace connaisseur --image=securesystemsengineering/testimage:unsigned >output.log 2>&1 || true

if [[ ! "$(cat output.log)" =~ 'Unable to find signed digest for image docker.io/securesystemsengineering/testimage:unsigned.' ]]; then
  echo 'Failed to deny unsigned image or failed with unexpected error. Output:'
  cat output.log
  exit 1
else
  echo 'Successfully denied usage of unsigned image'
fi

echo 'Testing signed image in unlabelled namespace...'
kubectl run pod --namespace connaisseur --image=securesystemsengineering/testimage:signed -lapp.kubernetes.io/instance=connaisseur >output.log 2>&1 || true

if [[ "$(cat output.log)" != 'pod/pod created' ]]; then
  echo 'Failed to allow signed image. Output:'
  cat output.log
  exit 1
else
  echo 'Successfully allowed usage of signed image'
fi

echo 'Testing unsigned image in ignored namespace...'
kubectl run pod --namespace ignoredns --image=securesystemsengineering/testimage:unsigned -lapp.kubernetes.io/instance=connaisseur >output.log 2>&1 || true

if [[ "$(cat output.log)" != 'pod/pod created' ]]; then
  echo 'Failed to allow unsigned image in ignored namespace. Output:'
  cat output.log
  exit 1
else
  echo 'Successfully allowed usage of unsigned image in ignored namespace'
fi

echo '### Testing "validate" label ###'

yq e '.namespacedValidation.mode="validate"' -i "helm/values.yaml"

echo 'Upgrading Connaisseur again...'
helm upgrade connaisseur helm --wait --namespace connaisseur || { echo 'Failed to upgrade Connaisseur'; exit 1; }
echo 'Successfully upgrade Connaisseur again'

echo 'Testing unsigned image in enabled namespace...'
kubectl run pod --namespace validatedns --image=securesystemsengineering/testimage:unsigned >output.log 2>&1 || true

if [[ ! "$(cat output.log)" =~ 'Unable to find signed digest for image docker.io/securesystemsengineering/testimage:unsigned.' ]]; then
  echo 'Failed to deny unsigned image or failed with unexpected error. Output:'
  cat output.log
  exit 1
else
  echo 'Successfully denied usage of unsigned image'
fi

echo 'Testing signed image in enabled namespace...'
kubectl run pod --namespace validatedns --image=securesystemsengineering/testimage:signed -lapp.kubernetes.io/instance=connaisseur >output.log 2>&1 || true

if [[ "$(cat output.log)" != 'pod/pod created' ]]; then
  echo 'Failed to allow signed image. Output:'
  cat output.log
  exit 1
else
  echo 'Successfully allowed usage of signed image'
fi

echo 'Testing unsigned image in unlabelled namespace...'
kubectl run pod2 --namespace connaisseur --image=securesystemsengineering/testimage:unsigned -lapp.kubernetes.io/instance=connaisseur >output.log 2>&1 || true

if [[ "$(cat output.log)" != 'pod/pod2 created' ]]; then
  echo 'Failed to allow unsigned image in ignored namespace. Output:'
  cat output.log
  exit 1
else
  echo 'Successfully allowed usage of unsigned image in ignored namespace'
fi

echo 'Uninstalling Connaisseur...'
# 'make' is chosen deliberately below to test the Makefile, while other tests use 'helm' directly
make uninstall || { echo 'Failed to uninstall Connaisseur'; exit 1; }
echo 'Successfully uninstalled Connaisseur'

rm output.log
echo 'Passed integration test'
