NAMESPACE = connaisseur
IMAGE := $(shell yq e '.deployment.image' helm/values.yaml)
HELM_HOOK_IMAGE := $(shell yq e '.deployment.helmHookImage' helm/values.yaml)
CLUSTER := $(shell CONTEXT=`kubectl config current-context` && kubectl config view -ojson | jq --arg CONTEXT $$CONTEXT '.contexts[] | select(.name==$$CONTEXT) | .context.cluster')
COSIGN_VERSION = 0.2.0

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
	helm install connaisseur helm --atomic --create-namespace --namespace $(NAMESPACE) --set alerting.cluster=$(CLUSTER)

uninstall:
	kubectl config set-context --current --namespace $(NAMESPACE)
	helm uninstall connaisseur
	kubectl delete ns connaisseur

upgrade:
	kubectl config set-context --current --namespace $(NAMESPACE)
	helm upgrade connaisseur helm --wait --set alerting.cluster=$(CLUSTER)

annihilate:
	kubectl delete all,mutatingwebhookconfigurations,clusterroles,clusterrolebindings,configmaps,imagepolicies,secrets -lapp.kubernetes.io/instance=connaisseur
