#!/usr/bin/env bash
set -u # TODO: why no eopipefail? answer: copy pasta from code YOU (yes you) have written, so you tell me
index=$1

templatef=$(mktemp)
deployf=$(mktemp)

yq e "." test/integration/load/load.yaml >${templatef}
index=${index} envsubst <${templatef} >${deployf}

kubectl apply -f ${deployf}
