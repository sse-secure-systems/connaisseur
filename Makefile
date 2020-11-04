NAMESPACE = connaisseur
IMAGE = $(IMAGE_NAME):$(TAG)
IMAGE_NAME = securesystemsengineering/connaisseur
TAG = v1.3.1

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
	helm install connaisseur helm --wait

uninstall:
	kubectl config set-context --current --namespace $(NAMESPACE)
	helm uninstall connaisseur
	kubectl delete ns $(NAMESPACE) --timeout=120s

upgrade:
	kubectl config set-context --current --namespace $(NAMESPACE)
	helm upgrade connaisseur helm --wait

annihilate:
	kubectl delete all,mutatingwebhookconfigurations,clusterroles,clusterrolebindings,configmaps,imagepolicies -lapp.kubernetes.io/instance=connaisseur
