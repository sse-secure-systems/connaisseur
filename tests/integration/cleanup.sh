#!/usr/bin/env bash
set -euo pipefail

preserve_info_and_cleanup() {
	kubectl config use-context ${DEFAULT_CTX}
	echo "Preserving log files..."
	(kubectl logs -n connaisseur -lapp.kubernetes.io/name=connaisseur --prefix=true --tail=-1 2>&1 || kubectl logs -n security -lapp.kubernetes.io/name=connaisseur --prefix=true --tail=-1 ) > connaisseur.log
	cat helm/values.yaml > connaisseur.conf
	( (kubectl describe pods -n connaisseur -lapp.kubernetes.io/name=connaisseur 2>&1 &&
	  kubectl describe deployments.apps -n connaisseur -lapp.kubernetes.io/name=connaisseur 2>&1) ||
	  (kubectl describe pods -n security -lapp.kubernetes.io/name=connaisseur &&
      kubectl describe deployments.apps -n security -lapp.kubernetes.io/name=connaisseur)) > connaisseur.state
    echo 'Cleaning up installation and test resources...'
    make uninstall >/dev/null 2>&1 || true
    helm uninstall connaisseur -n security >/dev/null 2>&1 || true
    kubectl delete ns security >/dev/null 2>&1 || true
    kubectl delete clusterrole auxillary >/dev/null 2>&1 || true
    kubectl delete clusterrolebinding securityadmin >/dev/null 2>&1 || true
    kubectl config delete-context deployconnaisseur >/dev/null 2>&1 || true
    kubectl delete all,cronjobs,daemonsets,jobs,replicationcontrollers,statefulsets,namespaces -luse="connaisseur-integration-test" -A >/dev/null 2>&1 || true
    kubectl delete ns connaisseur >/dev/null 2>&1 || true
    rm ghcr-values ghcr-validator >/dev/null 2>&1 || true
    rm release.yaml release_patched.yaml >/dev/null 2>&1 || true
    rm root.json >/dev/null 2>&1 || true
    mv values.yaml.backup helm/values.yaml >/dev/null 2>&1 || true
    mv deployment.yaml.backup helm/templates/deployment.yaml >/dev/null 2>&1 || true
    echo 'Finished cleanup of integration test leftovers.'
}
