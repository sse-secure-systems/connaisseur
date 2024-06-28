#!/usr/bin/env bash
set -euo pipefail
index=$1

templatef=$(mktemp)
deployf=$(mktemp)

yq e "." test/integration/load/load.yaml >${templatef}
index=${index} envsubst <${templatef} >${deployf}

kubectl apply -f ${deployf} || true
