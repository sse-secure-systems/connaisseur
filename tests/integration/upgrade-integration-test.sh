#!/usr/bin/env bash
set -euo pipefail

# This script is expected to be called from the root folder of Connaisseur

# Creating a random index to label the pods and avoid name collision for repeated runs
RAND=$(head -c 5 /dev/urandom | hexdump -ve '1/1 "%.2x"')
RETRY=3

echo 'Testing nv1 unsigned image...'
i=0
# should the webhook not be callable, retry twice
while : ; do
  i=$((i+1))
  kubectl run pod-${RAND} --image=securesystemsengineering/testimage:unsigned >output.log 2>&1 || true
  [[ ("$(cat output.log)" =~ "failed calling webhook") && $i -lt $RETRY ]] || break
done
RETRY=$((RETRY-1))

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
i=0
# should the webhook not be callable, retry once
while : ; do
  i=$((i+1))
  kubectl run npod-${RAND} --image=securesystemsengineering/testimage:signed -lapp.kubernetes.io/instance=connaisseur >output.log 2>&1 || true
  [[ ("$(cat output.log)" =~ "failed calling webhook") && $i -lt $RETRY ]] || break
done

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
