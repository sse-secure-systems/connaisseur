#! /bin/bash
set -euo pipefail

# This script is expected to be called from the root folder of Connaisseur

echo 'Preparing Connaisseur config...'
yq eval-all --inplace 'select(fileIndex == 0) * select(fileIndex == 1)' helm/values.yaml tests/integration/deployment-update.yaml
echo 'Config set'

echo 'Installing Connaisseur...'
helm install connaisseur helm --atomic --create-namespace --namespace connaisseur || { echo 'Failed to install Connaisseur'; exit 1; }
echo 'Successfully installed Connaisseur'

echo 'Testing 1 signed image deployment...'
kubectl apply -f tests/integration/deployments/deployment_i1.yaml >output.log 2>&1 || true

if [[ ! "$(cat output.log)" =~ 'deployment.apps/i1-deployment created' ]]; then
  echo 'Failed to allow deployment with signed image or failed with unexpected error. Output:'
  cat output.log
  exit 1
else
  echo 'Successfully allowed deployment'
fi

echo 'Testing 1 unsigned image deployment...'
kubectl apply -f tests/integration/deployments/deployment_i1u1.yaml >output.log 2>&1 || true

if [[ ! "$(cat output.log)" =~ 'denied the request: Unable to find signed digest' ]]; then
  echo 'Failed to deny deployment with unsigned image or failed with unexpected error. Output:'
  cat output.log
  exit 1
else
  echo 'Successfully denied deployment'
fi

echo 'Testing 1 nonexistent image (cosign) deployment...'
kubectl apply -f tests/integration/deployments/deployment_i1n1.yaml >output.log 2>&1 || true

if [[ ! "$(cat output.log)" =~ 'MANIFEST_UNKNOWN' ]]; then
  echo 'Failed to deny deployment with nonexistent image or failed with unexpected error. Output:'
  cat output.log
  exit 1
else
  echo 'Successfully denied deployment'
fi

echo 'Testing 2 signed images deployment...'
kubectl apply -f tests/integration/deployments/deployment_i2.yaml >output.log 2>&1 || true

if [[ ! "$(cat output.log)" =~ 'deployment.apps/i2-deployment created' ]]; then
  echo 'Failed to allow deployment with signed images or failed with unexpected error. Output:'
  cat output.log
  exit 1
else
  echo 'Successfully allowed deployment'
fi

echo 'Testing 1 signed image (first) and 1 unsigned (second) image deployment...'
kubectl apply -f tests/integration/deployments/deployment_i2u1-2.yaml >output.log 2>&1 || true

if [[ ! "$(cat output.log)" =~ 'denied the request: Unable to find signed digest' ]]; then
  echo 'Failed to deny deployment with unsigned image or failed with unexpected error. Output:'
  cat output.log
  exit 1
else
  echo 'Successfully denied deployment'
fi

echo 'Testing 1 signed image (second) and 1 unsigned (first) image deployment...'
kubectl apply -f tests/integration/deployments/deployment_i2u1-1.yaml >output.log 2>&1 || true

if [[ ! "$(cat output.log)" =~ 'denied the request: No trust data' ]]; then
  echo 'Failed to deny deployment with unsigned image or failed with unexpected error. Output:'
  cat output.log
  exit 1
else
  echo 'Successfully denied deployment'
fi

echo 'Testing 1 signed image (first) and 1 unsigned (second) image deployment...'
kubectl apply -f tests/integration/deployments/deployment_i2u1-2.yaml >output.log 2>&1 || true

if [[ ! "$(cat output.log)" =~ 'denied the request: Unable to find signed digest' ]]; then
  echo 'Failed to deny deployment with unsigned image or failed with unexpected error. Output:'
  cat output.log
  exit 1
else
  echo 'Successfully denied deployment'
fi

echo 'Testing 2 unsigned images deployment...'
kubectl apply -f tests/integration/deployments/deployment_i2u2.yaml >output.log 2>&1 || true

if [[ ! "$(cat output.log)" =~ 'denied the request:' ]]; then
  echo 'Failed to deny deployment with unsigned images or failed with unexpected error. Output:'
  cat output.log
  exit 1
else
  echo 'Successfully denied deployment'
fi

echo 'Testing 2 signed images and 1 signed init container deployment...'
kubectl apply -f tests/integration/deployments/deployment_i2i.yaml >output.log 2>&1 || true

if [[ ! "$(cat output.log)" =~ 'deployment.apps/i2i-deployment created' ]]; then
  echo 'Failed to allow deployment with signed images or failed with unexpected error. Output:'
  cat output.log
  exit 1
else
  echo 'Successfully allowed deployment'
fi

echo 'Testing 2 signed images and 1 unsigned init container deployment...'
kubectl apply -f tests/integration/deployments/deployment_i2ui.yaml >output.log 2>&1 || true

if [[ ! "$(cat output.log)" =~ 'denied the request: Unable to find signed digest for image' ]]; then
  echo 'Failed to deny deployment with unsigned images or failed with unexpected error. Output:'
  cat output.log
  exit 1
else
  echo 'Successfully denied deployment'
fi

echo 'Uninstalling Connaisseur...'
helm uninstall connaisseur --namespace connaisseur || { echo 'Failed to uninstall Connaisseur'; exit 1; }

echo 'Successfully uninstalled Connaisseur'

rm output.log
echo 'Passed integration test'
