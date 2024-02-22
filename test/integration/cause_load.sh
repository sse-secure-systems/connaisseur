#!/usr/bin/env bash
set -euo pipefail

index=$1

tmpf=$(mktemp)
index=${index} envsubst <test/integration/loadtest.yaml.template >${tmpf}

kubectl apply -f ${tmpf}
