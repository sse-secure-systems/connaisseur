until kubectl get mutatingwebhookconfigurations.admissionregistration.k8s.io | grep ${CONNAISSEUR_WEBHOOK}
do
  sleep 0.1
done