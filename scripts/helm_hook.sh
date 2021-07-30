if [ -z "$1" ]
then
    echo "You need to provide and command: install, upgrade, delete."
    exit 1
fi

if [ "$1" == "install" ]
then
    echo "installing ..."
    DEPLOYMENT=$(kubectl -n ${CONNAISSEUR_NAMESPACE} get deployments.apps -lapp.kubernetes.io/instance=connaisseur -o=jsonpath='{.items[*].metadata.name}')
    kubectl wait --for=condition=available --timeout=600s deployments.apps/${DEPLOYMENT} -n ${CONNAISSEUR_NAMESPACE}
    kubectl apply -f /data/webhook.yaml
    kubectl delete pod -lapp.kubernetes.io/service=bootstrap -n ${CONNAISSEUR_NAMESPACE} --force=true
    echo "done."
elif [ "$1" == "upgrade" ]
then
    echo "upgrading ..."
    DEPLOYMENT=$(kubectl -n ${CONNAISSEUR_NAMESPACE} get deployments.apps -lapp.kubernetes.io/instance=connaisseur -o=jsonpath='{.items[*].metadata.name}')
    kubectl rollout status ${DEPLOYMENT} -n ${CONNAISSEUR_NAMESPACE}
    kubectl apply -f /data/webhook.yaml
    kubectl delete pod -lapp.kubernetes.io/service=bootstrap -n ${CONNAISSEUR_NAMESPACE} --force=true
    echo "done."
elif [ "$1" == "delete" ]
then 
    echo "deleting ..."
    WEBHOOK=$(kubectl -n ${CONNAISSEUR_NAMESPACE} get mutatingwebhookconfigurations.admissionregistration.k8s.io -lapp.kubernetes.io/instance=connaisseur -o=jsonpath='{.items[*].metadata.name}')
    kubectl delete mutatingwebhookconfigurations.admissionregistration.k8s.io ${WEBHOOK}
    echo "done."
else 
    echo "Command not supported: $1"
    exit 1
fi
