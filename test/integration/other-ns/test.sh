#!/usr/bin/env bash
set -euo pipefail

other_ns_test() {
    setup
    install "helm" ${NS} "" false
    single_test "other-ns-01-unsigned" "Testing unsigned image..." "deploy" "securesystemsengineering/testimage:unsigned" "${NS}" "error during notaryv1 validation" "null"
    kubectl config use-context "${DEFAULT_CTX}"
    cleanup_other_ns
}

setup() {
    CLUSTER_NAME=$(kubectl config get-contexts $(kubectl config current-context) --no-headers | awk '{print $3}')
    CTX=deployconnaisseur
    NAME=securityadmin
    NS=security
    DEFAULT_CTX=$(kubectl config current-context)

    kubectl create ns ${NS}
    # Create service account with all permission on one namespace and some other, but non on other namespaces
    kubectl create serviceaccount ${NAME} --namespace=${NS}
    kubectl create rolebinding ${NAME} --clusterrole=cluster-admin --serviceaccount=${NS}:${NAME} --namespace=${NS}
    kubectl create clusterrole auxillary --verb='*' --resource=clusterrole,clusterrolebinding,mutatingwebhookconfigurations
    kubectl create clusterrolebinding ${NAME} --clusterrole=auxillary --serviceaccount=${NS}:${NAME}

    # Use that service account's config to run the Connaisseur deployment to see no other namespace is touched
    TOKEN=$(kubectl create token ${NAME} --namespace=${NS})
    kubectl config set-credentials ${CTX} --token="${TOKEN}"
    kubectl config set-context ${CTX} --cluster="${CLUSTER_NAME}" --user=${CTX}
    kubectl config use-context ${CTX}
}

cleanup_other_ns() {
    uninstall "helm" ${NS}
    kubectl delete clusterrole auxillary >/dev/null || true
    kubectl delete clusterrolebinding ${NAME} >/dev/null || true
    kubectl delete ns ${NS} >/dev/null || true
}
