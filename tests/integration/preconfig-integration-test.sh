#! /bin/bash
set -euo pipefail

# This script is expected to be called from the root folder of Connaisseur

echo 'Preparing Connaisseur config...'
yq eval-all --inplace 'select(fileIndex == 0) * select(fileIndex == 1)' helm/values.yaml tests/integration/preconfig-update.yaml
# exclude Connaisseur helm-hook from validation, as is not generally signed at the time of testing
yq e '.policy +={"pattern": "docker.io/securesystemsengineering/connaisseur:helm-hook-*"} | .policy[4].pattern style="double"' -i helm/values.yaml
yq e '.policy[4].validator = "allow"' -i helm/values.yaml
echo 'Config set'

echo 'Installing Connaisseur...'
helm install connaisseur helm --atomic || { echo 'Failed to install Connaisseur'; exit 1; }
echo 'Successfully installed Connaisseur'

echo 'Testing nv1 unsigned image...'
kubectl run pod --image=securesystemsengineering/testimage:unsigned >output.log 2>&1 || true

if [[ ! "$(cat output.log)" =~ 'Unable to find signed digest for image docker.io/securesystemsengineering/testimage:unsigned.' ]]; then
  echo 'Failed to deny unsigned image or failed with unexpected error. Output:'
  cat output.log
  exit 1
else
  echo 'Successfully denied usage of unsigned image'
fi

echo 'Testing nv1 signed image...'
kubectl run npod --image=securesystemsengineering/testimage:signed >output.log 2>&1 || true

if [[ "$(cat output.log)" != 'pod/npod created' ]]; then
  echo 'Failed to allow signed image. Output:'
  cat output.log
  exit 1
else
  echo 'Successfully allowed usage of signed image'
fi

echo 'Testing signed official docker image...'
kubectl run dpod --image=docker.io/library/hello-world >output.log 2>&1 || true

if [[ "$(cat output.log)" != 'pod/dpod created' ]]; then
  echo 'Failed to allow signed image. Output:'
  cat output.log
  exit 1
else
  echo 'Successfully allowed usage of signed image'
fi

echo 'Uninstalling Connaisseur...'
helm uninstall connaisseur || { echo 'Failed to uninstall Connaisseur'; exit 1; }
echo 'Successfully uninstalled Connaisseur'

rm output.log
echo 'Passed preconfig integration test'
