#!/usr/bin/env bash
set -euo pipefail

self_hosted_notary_test() {
    if [[ "${CI-}" != "true" ]]; then
        setup_self_hosted_notary
    fi
    update_for_self_hosted_notary
    render_notary_host
    install "make"
    multi_test "self-hosted-notary/cases.yaml"
    uninstall "make"
    cleanup_self_hosted_notary
}

setup_self_hosted_notary() {
    if search_for_minikube; then
        # minikube
        NETWORK=$(docker container inspect minikube | jq -r '.[].NetworkSettings.Networks | to_entries | .[].key')
        echo "Found minikube network: ${NETWORK}"
    else
        # kind
        NETWORK=$(docker container inspect kind-control-plane | jq -r '.[].NetworkSettings.Networks | to_entries | .[].key')
        echo "Found kind network: ${NETWORK}"
    fi

    if [[ -z "${NETWORK}" ]]; then
        echo "Failed to find network for self-hosted-notary endpoint."
        exit 1
    fi

    echo "Spinning up notary containers..."
    docker pull docker.io/securesystemsengineering/testimage:self-hosted-notary-signed
    PREFIXED_DIGEST=$(docker images --digests | grep self-hosted-notary-signed | awk '{print $3}')
    export DIGEST=$(echo ${PREFIXED_DIGEST#sha256:})
    docker run --rm -d --name notary-signer -p 7899:7899 -v ./test/integration/self-hosted-notary/notary-service-container/signer:/etc/docker/notary-signer/ --network "${NETWORK}" notary:signer -config=/etc/docker/notary-signer/config.json
    NOTARY_SIGNER_IP=$(docker container inspect notary-signer | jq -r --arg network "${NETWORK}" '.[].NetworkSettings.Networks[$network].IPAddress')
    docker run --rm -d --name notary-server -p 4443:4443 --add-host notary.signer:${NOTARY_SIGNER_IP} -v ./test/integration/self-hosted-notary/notary-service-container/server:/etc/docker/notary-server --network "${NETWORK}" notary:server -config=/etc/docker/notary-server/config.json -logf=json
    export NOTARY_SERVER_IP=$(docker container inspect notary-server | jq -r --arg network "${NETWORK}" '.[].NetworkSettings.Networks[$network].IPAddress')
    cd test/integration/self-hosted-notary
    docker build --build-arg "DIGEST=${DIGEST}" -f Dockerfile.populate_notary . -t populate-notary
    cd -
    docker run --rm --network "${NETWORK}" --add-host notary.server:${NOTARY_SERVER_IP} populate-notary
    export NOTARY_IP=${NOTARY_SERVER_IP}
    echo "Done spinning up notary..."
}

update_for_self_hosted_notary() {
    update_with_file "self-hosted-notary/install.yaml"
    curl -k "https://${NOTARY_IP}:4443/v2/docker.io/securesystemsengineering/testimage/_trust/tuf/root.json" > root.json
	SELF_HOSTED_NOTARY_PUBLIC_ROOT_KEY_ID=$(cat root.json | jq -r .signatures[0].keyid)
	cat root.json | jq -r --arg KEYID ${SELF_HOSTED_NOTARY_PUBLIC_ROOT_KEY_ID} '.signed.keys | .[$KEYID] | .keyval.public' | base64 -d | openssl x509 -pubkey -noout > self_hosted_notary_root_key.pub
	yq -i '(.application.validators.[] | select(.name == "self-hosted-notary") | .trustRoots.[] | select(.name=="default") | .key) |= load_str("self_hosted_notary_root_key.pub")' charts/connaisseur/values.yaml
	rm self_hosted_notary_root_key.pub root.json
}

render_notary_host() {
	envsubst <test/integration/self-hosted-notary/deployment_update.yaml >update_deployment_with_host_alias.yaml
	# It is not possible to yq the deployment.yaml as it's not valid yaml due to the helm variables, thus the awk magic here
	HOST_ALIAS=$(cat update_deployment_with_host_alias.yaml)
	awk -v host_alias="${HOST_ALIAS}" '/    spec:/ { print; print host_alias; next }1' charts/connaisseur/templates/deployment.yaml > deployment.yaml
    cp charts/connaisseur/templates/deployment.yaml charts/connaisseur/deployment.yaml.bak
	mv deployment.yaml charts/connaisseur/templates/
	rm update_deployment_with_host_alias.yaml
}

cleanup_self_hosted_notary() {
    docker stop notary-signer >/dev/null 2>&1 || true
    docker stop notary-server >/dev/null 2>&1 || true
    docker stop populate-notary >/dev/null 2>&1 || true
}

