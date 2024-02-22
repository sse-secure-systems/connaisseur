#!/usr/bin/bash
# Running as Shell such that we don't need to install dependencies in last pipeline step

set -eu

DIFF_REF=$(git tag --sort=version:refname | tail -n2 | sed 'N;s/\n/.../')
COUNT=$(git log "${DIFF_REF}" --no-decorate --pretty=%s | cut -d ":" -f1 | grep -c sec || true)

if [[ ${COUNT} -gt 0 ]]; then
  echo """
annotations:
  artifacthub.io/containsSecurityUpdates: "true"
""" >> charts/connaisseur/Chart.yaml
fi
