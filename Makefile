NAMESPACE = connaisseur
IMAGE := $(shell yq e '.deployment.image' helm/values.yaml)
HELM_HOOK_IMAGE := $(shell yq e '.deployment.helmHookImage' helm/values.yaml)
COSIGN_VERSION = 1.0.0

.PHONY: all docker install unistall upgrade annihilate

all: docker install

docker:
	docker build --build-arg COSIGN_VERSION=$(COSIGN_VERSION) -f docker/Dockerfile -t $(IMAGE) .
	docker build -f docker/Dockerfile.hook -t $(HELM_HOOK_IMAGE) .

install:
	#
	#=============================================
	#
	# The installation may last up to 5 minutes.
	#
	#=============================================
	#
	helm install connaisseur helm --atomic --create-namespace --namespace $(NAMESPACE)

uninstall:
	kubectl config set-context --current --namespace $(NAMESPACE)
	helm uninstall connaisseur
	kubectl delete ns connaisseur

upgrade:
	kubectl config set-context --current --namespace $(NAMESPACE)
	helm upgrade connaisseur helm --wait

annihilate:
	kubectl delete all,mutatingwebhookconfigurations,clusterroles,clusterrolebindings,configmaps,imagepolicies,secrets,serviceaccounts,crds -lapp.kubernetes.io/instance=connaisseur
	kubectl delete ns $(NAMESPACE)
