NAMESPACE = connaisseur
IMAGE_REPO := $(shell yq e '.kubernetes.deployment.image.repository' charts/connaisseur/values.yaml)
VERSION := $(shell yq e '.appVersion' charts/connaisseur/Chart.yaml)
KD := kubernetes.deployment
ALL_RS := all,mutatingwebhookconfigurations,clusterroles,clusterrolebindings,configmaps,secrets,serviceaccounts,crds

.PHONY: docker docker-multiarch install install-dev uninstall annihilate test upgrade kind-dev lint integration alerting

# meant for local building of docker image (single platform)
docker:
	docker buildx build --pull -f build/Dockerfile -t $(IMAGE_REPO):v$(VERSION) .

# build multi-architecture docker images (amd64, arm64)
# NOTE: buildx requires --push or --load; for multi-arch, must push to registry
docker-multiarch:
	docker buildx build --platform linux/amd64,linux/arm64 --pull -f build/Dockerfile -t $(IMAGE_REPO):v$(VERSION) --push .

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
	go test ./internal/... -race -coverprofile=cover.out -covermode=atomic; go tool cover -func cover.out

upgrade:
	helm upgrade connaisseur charts/connaisseur --namespace $(NAMESPACE) --wait

kind-dev:
	make docker && kind load docker-image $(IMAGE_REPO):v$(VERSION) && make install-dev

lint:
	golangci-lint run --exclude-dirs="test" --tests="false"

integration:
	bash "test/integration/main.sh" "regular"

alerting:
	cd test/integration/alerting && docker build -t securesystemsengineering/alerting-endpoint . && cd -

build-testimage-%:
	docker build --build-arg="MESSAGE=$*" -t securesystemsengineering/testimage:$* -f test/testdata/dockerfiles/Dockerfile test/testdata/dockerfiles
