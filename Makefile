NAMESPACE = connaisseur
IMAGE_REPO := $(shell yq e '.kubernetes.deployment.image.repository' charts/connaisseur/values.yaml)
VERSION := $(shell yq e '.appVersion' charts/connaisseur/Chart.yaml)
KD := kubernetes.deployment
ALL_RS := all,mutatingwebhookconfigurations,clusterroles,clusterrolebindings,configmaps,secrets,serviceaccounts,crds

.PHONY: docker install uninstall annihilate test install-dev upgrade lint

# meant for local building of docker image
docker:
	docker buildx build --pull -f build/Dockerfile -t $(IMAGE_REPO):v$(VERSION) .

install:
	helm install connaisseur charts/connaisseur --atomic --create-namespace --namespace $(NAMESPACE) $(HELM_ARGS)

install-dev:
	helm install --set $(KD).replicasCount=1,$(KD).pullPolicy=Never,application.logLevel=debug \
	 connaisseur charts/connaisseur --atomic --create-namespace --namespace $(NAMESPACE) $(HELM_ARGS)

uninstall:
	helm uninstall connaisseur -n $(NAMESPACE)
	kubectl delete ns $(NAMESPACE)

annihilate:
	kubectl delete $(ALL_RS) -lapp.kubernetes.io/instance=connaisseur -n $(NAMESPACE)
	kubectl delete imagepolicies -lapp.kubernetes.io/instance=connaisseur -n $(NAMESPACE) || true
	kubectl delete ns $(NAMESPACE)

test:
	go test ./... -race -coverprofile=cover.out -covermode=atomic; go tool cover -func cover.out

upgrade:
	helm upgrade connaisseur charts/connaisseur --namespace $(NAMESPACE) --wait

kind-int-test:
	./tests/integration/run_integration_tests.sh -c kind -r "regular cosign"

kind-dev:
	make docker && kind load docker-image $(IMAGE_REPO):v$(VERSION) && make install-dev

lint:
	golangci-lint run --skip-dirs="test"
