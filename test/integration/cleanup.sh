#!/usr/bin/env bash

cleanup() {
    RESOURCES="all,cronjobs,daemonsets,jobs,replicationcontrollers,statefulsets,namespaces"
    
    echo -n "Cleaning up ..."

    # delete all resources with the label "use=connaisseur-integration-test"
    if [[ !($(kubectl get $RESOURCES -luse="connaisseur-integration-test" -A) =~ "No resources found" ) ]]; then
        kubectl delete $RESOURCES -luse="connaisseur-integration-test" -A >/dev/null || true
    fi
    
    # delete the connaisseur namespace if it exists
    if [[ !($(kubectl get ns connaisseur 2>&1) =~ "not found") ]]; then
        kubectl delete ns connaisseur >/dev/null || true
    fi

    # delete the connaisseur-webhook mutating webhook configuration if it exists
    if [[ !($(kubectl get mutatingwebhookconfigurations) =~ "No resources found") ]]; then
        kubectl delete mutatingwebhookconfigurations connaisseur-webhook >/dev/null 2>&1 || true
    fi

    # restore the values.yaml file
    mv charts/connaisseur/values.yaml.bak charts/connaisseur/values.yaml >/dev/null

    success
}

preserve_and_cleanup() {
    rv=$?

    # if we are running in CI, we want to exit with the return value
    if [[ "${GITHUB_ACTIONS-}" == "true" ]]; then
        exit $rv
    fi

    # if the help message was printed, we just want to exit
    if [[ $rv == 2 ]]; then
        exit 0
    fi

    # if the integration test is still running, we want to preserve the log, state and values.yaml files
    # (this will be the case if the test was interrupted with SIGINT)
    if [[ ${IT_RUNNING} == "true" ]]; then
        echo -n "Preserving log, state and values.yaml files ..."
        
        kubectl logs -n connaisseur -lapp.kubernetes.io/name=connaisseur --prefix=true --tail=-1 > connaisseur.log || true
        cat charts/connaisseur/values.yaml > connaisseur.yaml || true
        (kubectl describe pods -n connaisseur -lapp.kubernetes.io/name=connaisseur 2>&1 &&
        kubectl describe deployments.apps -n connaisseur -lapp.kubernetes.io/name=connaisseur 2>&1) > connaisseur.state || true

        success
    fi

    # the actual cleanup
    cleanup

    exit $rv
}