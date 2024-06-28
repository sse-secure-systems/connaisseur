#!/usr/bin/env bash
set -euo pipefail

namespaced_validation_test() {
    create_namespaces
    update_with_file "namespaced/install.yaml"
    install "make"
    multi_test "namespaced/ignore_cases.yaml"

    update '.application.features.namespacedValidation.mode="validate"'
    upgrade "make"
    multi_test "namespaced/validated_cases.yaml"
}

create_namespaces() {
    echo -n "Creating namespaces..."
    kubectl create namespace ignoredns >/dev/null
    kubectl label ns ignoredns securesystemsengineering.connaisseur/webhook=ignore use=connaisseur-integration-test >/dev/null
    kubectl create namespace validatedns >/dev/null
    kubectl label ns validatedns securesystemsengineering.connaisseur/webhook=validate use=connaisseur-integration-test >/dev/null
    echo -e "${SUCCESS}"
}
