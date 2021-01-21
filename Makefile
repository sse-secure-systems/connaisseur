NAMESPACE = connaisseur
IMAGE := $(shell yq e '.deployment.image' helm/values.yaml)
HELM_HOOK_IMAGE := $(shell yq e '.deployment.helmHookImage' helm/values.yaml)

.PHONY: all docker certs install unistall upgrade annihilate

all: docker install

docker:
	docker build -f docker/Dockerfile -t $(IMAGE) .
	docker build -f docker/Dockerfile.hook -t $(HELM_HOOK_IMAGE) .

certs:
	bash helm/certs/gen_certs.sh

install: certs
	kubectl create ns $(NAMESPACE) || true
	kubectl config set-context --current --namespace $(NAMESPACE)
	#
	#=============================================
	#
	# The installation may last up to 5 minutes.
	#
	#=============================================
	#
	helm install connaisseur helm --atomic

uninstall:
	kubectl config set-context --current --namespace $(NAMESPACE)
	helm uninstall connaisseur
	kubectl delete ns connaisseur

upgrade:
	kubectl config set-context --current --namespace $(NAMESPACE)
	helm upgrade connaisseur helm --wait

annihilate:
	kubectl delete all,mutatingwebhookconfigurations,clusterroles,clusterrolebindings,configmaps,imagepolicies,secrets -lapp.kubernetes.io/instance=connaisseur
