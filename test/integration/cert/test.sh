#!/usr/bin/env bash
set -euo pipefail

cert_test() {
    install "make"
    multi_test "cert/cases.yaml"
    update_with_file "cert/update.yaml"
    upgrade "make"
    certificate_check
    multi_test "cert/cases.yaml"
    uninstall "make"
}
certificate_check() {
    # compare KEY from update.yaml with the one in the secret
    EXPT_KEY=$(yq e ".kubernetes.deployment.tls.key" test/integration/cert/update.yaml)
    GOTN_KEY=$(kubectl get secrets -n connaisseur connaisseur-tls -o json | jq -r '.data."tls.key"' | base64 -d)
    DIFF=$(diff <(echo "${EXPT_KEY}") <(echo "${GOTN_KEY}") || true)
    if [[ "${DIFF}" != "" ]]; then
        echo "Unexpected TLS key. Should be pre-configured one."
        EXIT=1
    else
        echo "Found expected TLS key."
    fi

    # compare CERT from update.yaml with the one in the secret
    EXPT_CRT=$(yq e ".kubernetes.deployment.tls.cert" test/integration/cert/update.yaml)
    GOTN_CRT=$(kubectl get secrets -n connaisseur connaisseur-tls -o json | jq -r '.data."tls.crt"' | base64 -d)
    DIFF=$(diff <(echo "${EXPT_CRT}") <(echo "${GOTN_CRT}") || true)
    if [[ "${DIFF}" != "" ]]; then
        echo "Unexpected TLS certificate. Should be pre-configured one."
        echo "DIFF: ${DIFF}"
        EXIT=1
    else
        echo "Found expected TLS certificate."
    fi
}
