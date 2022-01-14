#!/usr/bin/env bash
set -u
index=$1

tmpf=$(mktemp)
index=${index} envsubst <tests/integration/loadtest.yaml.template >${tmpf}

kubectl apply -f ${tmpf}
