NAMESPACE = connaisseur
IMAGE := $(shell yq r helm/values.yaml 'deployment.image')
IMAGE_NAME := $(shell echo $(IMAGE) | cut -d ':' -f1)

.PHONY: all docker certs install unistall upgrade annihilate

all: docker install

docker:
	docker build -f docker/Dockerfile -t $(IMAGE) .
	docker build -f docker/Dockerfile.hook -t $(IMAGE_NAME):helm-hook .

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
	kubectl delete ns $(NAMESPACE) --timeout=120s

upgrade:
	kubectl config set-context --current --namespace $(NAMESPACE)
	helm upgrade connaisseur helm --wait

annihilate:
	kubectl delete all,mutatingwebhookconfigurations,clusterroles,clusterrolebindings,configmaps,imagepolicies -lapp.kubernetes.io/instance=connaisseur
