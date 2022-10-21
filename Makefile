NAMESPACE = connaisseur
IMAGE := $(shell yq e '.deployment.image' helm/values.yaml)
COSIGN_VERSION = 1.13.1

.PHONY: all docker install uninstall upgrade annihilate

all: docker install

docker:
	docker build --pull --build-arg COSIGN_VERSION=$(COSIGN_VERSION) -f docker/Dockerfile -t $(IMAGE) .

install:
	#
	#=============================================
	#
	# The installation may last up to 5 minutes.
	#
	#=============================================
	#
	helm install connaisseur helm --atomic --create-namespace --namespace $(NAMESPACE)

dev-install:
	helm install --set deployment.replicasCount=1,deployment.imagePullPolicy=Never connaisseur helm --atomic --create-namespace --namespace $(NAMESPACE) 

uninstall:
	helm uninstall connaisseur -n $(NAMESPACE)
	kubectl delete ns $(NAMESPACE)

upgrade:
	helm upgrade connaisseur helm  -n $(NAMESPACE) --wait

annihilate:
	kubectl delete all,mutatingwebhookconfigurations,clusterroles,clusterrolebindings,configmaps,secrets,serviceaccounts,crds -lapp.kubernetes.io/instance=connaisseur -n $(NAMESPACE)
	kubectl delete imagepolicies -lapp.kubernetes.io/instance=connaisseur -n $(NAMESPACE) || true
	kubectl delete ns $(NAMESPACE)
