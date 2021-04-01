#! /bin/bash
set -euo pipefail

# This script is expected to be called from the root folder of Connaisseur

echo 'Preparing Connaisseur config...'
yq eval-all --inplace 'select(fileIndex == 0) * select(fileIndex == 1)' helm/values.yaml connaisseur/tests/integration/namespaced-update.yaml
echo 'Config set'

echo 'Installing Connaisseur...'
make install || { echo 'Failed to install Connaisseur'; exit 1; }
echo 'Successfully installed Connaisseur'

echo 'Testing unsigned image in protected namespace...'
kubectl run pod --namespace verifyns --image=securesystemsengineering/testimage:unsigned >output.log 2>&1 || true

if [[ "$(cat output.log)" != 'Error from server: admission webhook "connaisseur-svc.connaisseur.svc" denied the request: could not find signed digest for image "docker.io/securesystemsengineering/testimage:unsigned" in trust data.' ]]; then
  echo 'Failed to deny unsigned image or failed with unexpected error. Output:'
  cat output.log
  exit 1
else
  echo 'Successfully denied usage of unsigned image'
fi

echo 'Testing signed image in protected namespace...'
kubectl run pod --namespace verifyns --image=securesystemsengineering/testimage:signed >output.log 2>&1 || true

if [[ "$(cat output.log)" != 'pod/pod created' ]]; then
  echo 'Failed to allow signed image. Output:'
  cat output.log
  exit 1
else
  echo 'Successfully allowed usage of signed image'
fi

echo 'Testing unsigned image in unprotected namespace...'
kubectl run pod --image=securesystemsengineering/testimage:unsigned >output.log 2>&1 || true

if [[ "$(cat output.log)" != 'pod/pod created' ]]; then
  echo 'Failed to allow unsigned image in unprotected namespace. Output:'
  cat output.log
  exit 1
else
  echo 'Successfully allowed usage of unsigned image in unprotected namespace'
fi

echo 'Uninstalling Connaisseur...'
make uninstall || { echo 'Failed to uninstall Connaisseur'; exit 1; }
echo 'Successfully uninstalled Connaisseur'

rm output.log
echo 'Passed integration test'
