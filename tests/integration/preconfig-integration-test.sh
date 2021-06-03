#! /bin/bash
set -euo pipefail

# This script is expected to be called from the root folder of Connaisseur

echo 'Preparing Connaisseur config...'
yq eval-all --inplace 'select(fileIndex == 0) * select(fileIndex == 1)' helm/values.yaml tests/integration/preconfig-update.yaml
echo 'Config set'

echo 'Installing Connaisseur...'
make install || { echo 'Failed to install Connaisseur'; exit 1; }
echo 'Successfully installed Connaisseur'

echo 'Testing cosign unsigned image...'
kubectl run pod --image=securesystemsengineering/testimage:co-unsigned >output.log 2>&1 || true

if [[ ! "$(cat output.log)" =~ 'No trust data for image "docker.io/securesystemsengineering/testimage:co-unsigned".' ]]; then
  echo 'Failed to deny unsigned image or failed with unexpected error. Output:'
  cat output.log
  exit 1
else
  echo 'Successfully denied usage of cosign unsigned image'
fi

echo 'Testing cosign signed image...'
kubectl run cpod --image=securesystemsengineering/testimage:co-signed >output.log 2>&1 || true

if [[ "$(cat output.log)" != 'pod/cpod created' ]]; then
  echo 'Failed to allow signed image. Output:'
  cat output.log
  exit 1
else
  echo 'Successfully allowed usage of signed image'
fi

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
make uninstall || { echo 'Failed to uninstall Connaisseur'; exit 1; }
echo 'Successfully uninstalled Connaisseur'

rm output.log
echo 'Passed preconfig integration test'
