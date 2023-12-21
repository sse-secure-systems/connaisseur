NAMESPACE = connaisseur
IMAGE_REPOSITORY := $(shell yq e '.kubernetes.deployment.image.repository' helm/values.yaml)
VERSION := $(shell yq e '.appVersion' helm/Chart.yaml)
COSIGN_VERSION = 2.2.2

.PHONY: all docker install uninstall upgrade annihilate

all: docker install

docker:
	docker build --pull --build-arg COSIGN_VERSION=$(COSIGN_VERSION) -f docker/Dockerfile -t $(IMAGE_REPOSITORY):v$(VERSION) .

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
	helm install --set kubernetes.deployment.replicasCount=1,kubernetes.deployment.imagePullPolicy=Never,application.logLevel=DEBUG connaisseur helm --atomic --create-namespace --namespace $(NAMESPACE)

uninstall:
	helm uninstall connaisseur -n $(NAMESPACE)
	kubectl delete ns $(NAMESPACE)

upgrade:
	helm upgrade connaisseur helm -n $(NAMESPACE) --wait

annihilate:
	kubectl delete all,mutatingwebhookconfigurations,clusterroles,clusterrolebindings,configmaps,secrets,serviceaccounts,crds -lapp.kubernetes.io/instance=connaisseur -n $(NAMESPACE)
	kubectl delete imagepolicies -lapp.kubernetes.io/instance=connaisseur -n $(NAMESPACE) || true
	kubectl delete ns $(NAMESPACE)
