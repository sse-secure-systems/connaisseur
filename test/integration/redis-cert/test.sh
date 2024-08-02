#!/usr/bin/env bash
set -euo pipefail

redis_cert_test() {
    # install connaisseur without redis cert
    update_with_file "redis-cert/install.yaml"
    install "make"

    # wait for redis to be ready
    wait_for_redis

    # create same image twice
    single_test "redis-cert-01-signed" "Testing signed nv1 image..." "deploy" "securesystemsengineering/testimage:signed" "default" "" "null"
    single_test "redis-cert-02-cached" "Testing signed nv1 image using cache..." "deploy" "securesystemsengineering/testimage:signed" "default" "" "null"
    kubectl logs -n connaisseur -lapp.kubernetes.io/instance=connaisseur > output.log

    # check for cache hit
    echo -n "Checking if cache hit was logged..."
    if grep -q "skipped validation: cache hit for image securesystemsengineering/testimage:signed" output.log; then
        echo -e ${SUCCESS}
    else 
        echo -e ${FAILED}
        EXIT="1"
    fi

    # update connaisseur with redis cert
    update_with_file "redis-cert/update.yaml"
    upgrade "make"

    # wait for redis to be ready
    wait_for_redis

    # create same image twice
    single_test "redis-cert-03-signed" "Testing signed nv1 image again..." "deploy" "securesystemsengineering/testimage:signed" "default" "" "null"
    single_test "redis-cert-04-cached" "Testing signed nv1 image using cache again..." "deploy" "securesystemsengineering/testimage:signed" "default" "" "null"
    kubectl logs -n connaisseur -lapp.kubernetes.io/instance=connaisseur > output.log

    # check for cache hit
    echo -n  "Checking if cache hit was logged..."
    if grep -q "skipped validation: cache hit for image securesystemsengineering/testimage:signed" output.log; then
        echo -e ${SUCCESS}
    else 
        echo -e ${FAILED}
        EXIT="1"
    fi
    rm output.log
}

wait_for_redis() {
    timeout 30 bash -c '
    while true; do
        kubectl logs -n connaisseur -lapp.kubernetes.io/instance=redis --tail=-1 | grep -q  "Ready to accept connections tls" && break
        sleep 1
    done
    ' || true
}
