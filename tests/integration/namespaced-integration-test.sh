#! /bin/bash
set -euo pipefail

# This script is expected to be called from the root folder of Connaisseur

echo 'Creating test namespaces'
kubectl create namespace ignoredns
kubectl label ns ignoredns securesystemsengineering.connaisseur/webhook=ignore
kubectl create namespace validatedns
kubectl label ns validatedns securesystemsengineering.connaisseur/webhook=validate

echo 'Preparing Connaisseur config...'
yq eval-all --inplace 'select(fileIndex == 0) * select(fileIndex == 1)' helm/values.yaml tests/integration/namespaced-update.yaml
echo 'Config set'

echo '### Testing "ignore" label ###'

echo 'Installing Connaisseur...'
helm install connaisseur helm --atomic --create-namespace --namespace connaisseur || { echo 'Failed to install Connaisseur'; exit 1; }
echo 'Successfully installed Connaisseur'

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
kubectl run pod --namespace connaisseur --image=securesystemsengineering/testimage:signed >output.log 2>&1 || true

if [[ "$(cat output.log)" != 'pod/pod created' ]]; then
  echo 'Failed to allow signed image. Output:'
  cat output.log
  exit 1
else
  echo 'Successfully allowed usage of signed image'
fi

echo 'Testing unsigned image in ignored namespace...'
kubectl run pod --namespace ignoredns --image=securesystemsengineering/testimage:unsigned >output.log 2>&1 || true

if [[ "$(cat output.log)" != 'pod/pod created' ]]; then
  echo 'Failed to allow unsigned image in ignored namespace. Output:'
  cat output.log
  exit 1
else
  echo 'Successfully allowed usage of unsigned image in ignored namespace'
fi

echo 'Uninstalling Connaisseur...'
helm uninstall connaisseur --namespace connaisseur || { echo 'Failed to uninstall Connaisseur'; exit 1; }
kubectl delete ns connaisseur
echo 'Successfully uninstalled Connaisseur'

echo '### Testing "validate" label ###'

yq e '.namespacedValidation.mode="validate"' -i "helm/values.yaml"

echo 'Installing Connaisseur...'
helm install connaisseur helm --atomic --create-namespace --namespace connaisseur || { echo 'Failed to install Connaisseur'; exit 1; }
echo 'Successfully installed Connaisseur'

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
kubectl run pod --namespace validatedns --image=securesystemsengineering/testimage:signed >output.log 2>&1 || true

if [[ "$(cat output.log)" != 'pod/pod created' ]]; then
  echo 'Failed to allow signed image. Output:'
  cat output.log
  exit 1
else
  echo 'Successfully allowed usage of signed image'
fi

echo 'Testing unsigned image in unlabelled namespace...'
kubectl run pod --namespace connaisseur --image=securesystemsengineering/testimage:unsigned >output.log 2>&1 || true

if [[ "$(cat output.log)" != 'pod/pod created' ]]; then
  echo 'Failed to allow unsigned image in ignored namespace. Output:'
  cat output.log
  exit 1
else
  echo 'Successfully allowed usage of unsigned image in ignored namespace'
fi

echo 'Uninstalling Connaisseur...'
helm uninstall connaisseur --namespace connaisseur || { echo 'Failed to uninstall Connaisseur'; exit 1; }
echo 'Successfully uninstalled Connaisseur'

rm output.log
echo 'Passed integration test'
