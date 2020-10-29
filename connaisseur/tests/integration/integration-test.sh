#! /bin/bash
set -euo pipefail

envsubst <connaisseur/tests/integration/values.yaml >helm/values.yaml

make install || { echo "Failed to install Connaisseur"; exit 1; }
echo "Successfully installed Connaisseur"

kubectl create -f - << EOF >output.log 2>&1 || true
apiVersion: apps/v1
kind: Deployment
metadata:
  name: sample-deployment
  labels:
    app: sample
spec:
  selector:
    matchLabels:
      app: sample
  replicas: 1
  template:
    metadata:
      labels:
        app: sample
    spec:
      containers:
      - name: sample
        image: docker.io/connytest/testimage:unsigned
        imagePullPolicy: IfNotPresent
EOF

if [[ "$(cat output.log)" != 'Error from server: error when creating "STDIN": admission webhook "connaisseur-svc.connaisseur.svc" denied the request: could not find signed digest for image "docker.io/connytest/testimage:unsigned" in trust data.' ]]; then
  echo "Failed to deny unsigned deployment. Output of deployment:"
  cat output.log
  exit 1
else
  echo "Successfully denied usage of unsigned image"
fi

kubectl create -f - << EOF >output.log 2>&1 || true
apiVersion: apps/v1
kind: Deployment
metadata:
  name: sample-deployment
  labels:
    app: sample
spec:
  selector:
    matchLabels:
      app: sample
  replicas: 1
  template:
    metadata:
      labels:
        app: sample
    spec:
      containers:
      - name: sample
        image: docker.io/connytest/testimage:signed
        imagePullPolicy: IfNotPresent
EOF

if [[ "$(cat output.log)" != 'deployment.apps/sample-deployment created' ]]; then
  echo "Failed to allow signed image. Output of deployment:"
  cat output.log
  exit 1
else
  echo "Successfully allowed usage of signed image"
fi

make uninstall || { echo "Failed to uninstall Connaisseur"; exit 1; }
echo "Successfully uninstalled Connaisseur"

rm output.log
echo "Passed integration test"
