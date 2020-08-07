if [ -z "$1" ]
then
    echo "You need to provide and command: install, upgrade, delete."
    exit 1
fi

if [ "$1" == "install" ]
then
    echo "installing ..."
    DEPLOYMENT=$(kubectl -n connaisseur get deployments.apps -lapp.kubernetes.io/instance=connaisseur -o=jsonpath='{.items[*].metadata.name}')
    kubectl wait --for=condition=available --timeout=600s deployments.apps/$DEPLOYMENT -n connaisseur
    kubectl apply -f /data/webhook.yaml
    echo "done."
elif [ "$1" == "upgrade" ]
then
    echo "upgrading ..."
    DEPLOYMENT=$(kubectl -n connaisseur get deployments.apps -lapp.kubernetes.io/instance=connaisseur -o=jsonpath='{.items[*].metadata.name}')
    kubectl rollout status $DEPLOYMENT
    kubectl apply -f /data/webhook.yaml
    echo "done."
elif [ "$1" == "delete" ]
then 
    echo "deleting ..."
    WEBHOOK=$(kubectl -n connaisseur get mutatingwebhookconfigurations.admissionregistration.k8s.io -lapp.kubernetes.io/instance=connaisseur -o=jsonpath='{.items[*].metadata.name}')
    kubectl delete mutatingwebhookconfigurations.admissionregistration.k8s.io $WEBHOOK
    echo "done."
else 
    echo "Command not supported: $1"
    exit 1
fi