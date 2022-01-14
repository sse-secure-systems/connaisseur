#!/usr/bin/env bash
set -euo pipefail

# This script is expected to be called from the root folder of Connaisseur

# Creating a random index to label the pods and avoid name collision for repeated runs
RAND=$(head -c 5 /dev/urandom | hexdump -ve '1/1 "%.2x"')

echo 'Testing nv1 unsigned image...'
kubectl run pod-${RAND} --image=securesystemsengineering/testimage:unsigned >output.log 2>&1 || true

if [[ ! "$(cat output.log)" =~ 'Unable to find signed digest for image docker.io/securesystemsengineering/testimage:unsigned.' ]]; then
  echo 'Failed to deny unsigned image or failed with unexpected error. Output:'
  cat output.log
  kubectl logs -n connaisseur deployment/connaisseur-deployment > output.log
  cat output.log
  exit 1
else
  echo 'Successfully denied usage of unsigned image'
fi

echo 'Testing nv1 signed image...'
kubectl run npod-${RAND} --image=securesystemsengineering/testimage:signed -lapp.kubernetes.io/instance=connaisseur >output.log 2>&1 || true

if [[ "$(cat output.log)" != "pod/npod-${RAND} created" ]]; then
  echo 'Failed to allow signed image. Output:'
  cat output.log
  exit 1
else
  echo 'Successfully allowed usage of signed image'
fi

echo 'Testing signed official docker image...'
kubectl run dpod-${RAND} --image=docker.io/library/hello-world -lapp.kubernetes.io/instance=connaisseur >output.log 2>&1 || true

if [[ "$(cat output.log)" != "pod/dpod-${RAND} created" ]]; then
  echo 'Failed to allow signed image. Output:'
  cat output.log
  exit 1
else
  echo 'Successfully allowed usage of signed image'
fi

# Cleanup can be skipped in GitHub Actions
if [[ "${GITHUB_ACTIONS-}" != "true"  ]]; then
    kubectl delete pods --all || { echo 'Failed to delete test pods'; exit 1; }
fi

rm output.log
echo 'Passed upgrade integration test'
