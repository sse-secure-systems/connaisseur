#!/usr/bin/env bash
set -euo pipefail

## VARIABLES ------------------------------------------------------- ##

declare -A DEPLOYMENT_RES=(["ADMIT"]="0" ["REJECT"]="0")
RED="\033[0;31m"
GREEN="\033[0;32m"
NC="\033[0m"
SUCCESS="${GREEN}SUCCESS${NC}"
FAILED="${RED}FAILED${NC}"
RETRY=3

## UTILS ------------------------------------------------------- ##
fail() {
    echo -e "${FAILED}"
    exit 1
}

success() {
    echo -e "${SUCCESS}"
}

null_to_empty() {
    read in

    if [[ "$in" == "null" ]]; then
        echo ""
    else
        echo "$in"
    fi
}

ghcr_case() {
    if [[ -n "${IMAGE+x}" && -n "${IMAGEPULLSECRET+x}" && "${GITHUB_WORKFLOW}" != "release" ]]; then
        return 0
    fi
    return 1
}

trap_add() { # $1: command, $@: trap names
    trap_add_cmd=$1; shift
    for trap_add_name in "$@"; do
        trap -- "$(
            printf '%s\n%s\n' "$(trap -p "${trap_add_name}")" "${trap_add_cmd}"
        )" "${trap_add_name}"
    done
}

# set the trace attribute for the above function.  this is
# required to modify DEBUG or RETURN traps because functions don't
# inherit them unless the trace attribute is set
declare -f -t trap_add

search_for_minikube() {
    if [[ "$(docker inspect minikube 2> /dev/null | jq -r .[].State.Status || echo 'container not found')" != "running" ]]; then
        # maybe docker-env is set, so try again after unsetting it
        eval $(minikube docker-env -u) || true
        if [[ "$(docker inspect minikube 2> /dev/null | jq -r .[].State.Status || echo 'container not found')" != "running" ]]; then
            return 1
        else
            # flag to reset docker-env after test
            RESET_DOCKER_ENV="true"
            return 0
        fi
    else
        return 0
    fi
}

## INSTALLATIONS ---------------------------------------------- ##
install() { # $1: helm or make, $2: namespace, $3: additional helm args $4: create ns flag
    ARGS=$(printf '%s --set kubernetes.additionalLabels.use=connaisseur-integration-test' "${3:-}")

    if ghcr_case; then
        create_ghcr_image_pull_secret ${2:-connaisseur} ${4:-true}
    fi
    
    echo -n "Installing Connaisseur using $1..."
    case $1 in
    "helm")
        helm install connaisseur charts/connaisseur --atomic --namespace "${2:-connaisseur}" \
            ${ARGS} >/dev/null || fail
        ;;
    "make")
        make install NAMESPACE="${2:-connaisseur}" HELM_ARGS="${ARGS}" > /dev/null || fail
        ;;
    "release")
        helm repo add connaisseur https://sse-secure-systems.github.io/connaisseur/charts --force-update > /dev/null

        helm show values connaisseur/connaisseur > release.yaml
        if ghcr_case; then
            ghcr_update release.yaml
        fi
        helm install connaisseur connaisseur/connaisseur --atomic --namespace "${2:-connaisseur}" \
            --create-namespace --values release.yaml ${ARGS} >/dev/null || fail
        rm release.yaml
    ;;
    *)
        fail
        ;;
    esac
    success
}

uninstall() { # $1: helm or make or force, $2: namespace
    echo -n "Uninstalling Connaisseur using $1..."
    case $1 in
    "helm")
        helm uninstall connaisseur --namespace "${2:-connaisseur}" >/dev/null || fail
        ;;
    "make")
        make uninstall NAMESPACE="${2:-connaisseur}" >/dev/null || fail
        ;;
    "force")
        kubectl delete all,secrets,serviceaccounts,mutatingwebhookconfigurations,configmaps,namespaces \
                -lapp.kubernetes.io/instance=connaisseur -A --force --grace-period=0 >/dev/null 2>&1
        ;;
    *)
        fail
        ;;
    esac
    success
}

upgrade() { # $1: helm or make, $2: namespace
    echo -n "Upgrading Connaisseur using $1..."
    case $1 in
    "helm")
        helm upgrade connaisseur charts/connaisseur --wait \
            --namespace "${2:-connaisseur}" >/dev/null || fail
        ;;
    "make")
        make upgrade NAMESPACE="${2:-connaisseur}" >/dev/null || fail
        ;;
    *)
        fail
        ;;
    esac
    success
}

create_ghcr_image_pull_secret() { # $1: namespace, $2: create_flag
    if ${2:-true}; then
        echo -n "Creating namespace ${1:-connaisseur} ..."
        kubectl create namespace "${1:-connaisseur}" >/dev/null || fail
        success
    fi

    echo -n 'Creating image pull secret ...'
    kubectl create secret generic "${IMAGEPULLSECRET}" \
        --from-file=.dockerconfigjson="${HOME}"/.docker/config.json \
        --type=kubernetes.io/dockerconfigjson \
        --namespace "${1:-connaisseur}" >/dev/null || fail
    success
}

## UPDATES ----------------------------------------------------- ##

update() { # $@: update expressions
    for update in "$@"; do
        yq e -i "${update}" charts/connaisseur/values.yaml
    done
}

update_with_file() { # $1: file name relative to test/integration path
    envsubst <test/integration/$1 >update

    if ghcr_case; then
        ghcr_update update
    fi

    yq eval-all --inplace 'select(fileIndex == 0) * select(fileIndex == 1)' charts/connaisseur/values.yaml update
    rm update
}

ghcr_update() { # $1: file
    # set image and tag
    yq e -i '.kubernetes.deployment.image.repository = env(IMAGE)' $1
    yq e -i '.kubernetes.deployment.image.tag = env(TAG)' $1
    # add imagePullSecrets
    yq e -i '.kubernetes.deployment.image.imagePullSecrets[0].name = env(IMAGEPULLSECRET)' $1
    # add cosign validator:
    # name: connaisseur-ghcr
    #   type: cosign
    #   trustRoots:
    #     - name: default
    #       key: |-
    #         ${COSIGN_PUBLIC_KEY}
    #   auth:
    #     secretName: ${IMAGEPULLSECRET}
    export PKEY=${COSIGN_PUBLIC_KEY//$'<br>'/'\n'}
    export PKEY=$(echo -e $PKEY)
    yq e -i '.application.validators += [{"name":"connaisseur-ghcr","type":"cosign","trustRoots":[{"name":"default","key":strenv(PKEY)}],"auth":{"secretName":strenv(IMAGEPULLSECRET)}}]' $1
    # add policy for ghcr image
    yq e -i '.application.policy += [{"pattern":env(IMAGE)+":"+env(TAG),"validator":"connaisseur-ghcr"}]' $1
}



## TESTS ------------------------------------------------------- ##
single_test() { # ID TXT TYP REF NS MSG RES
    echo -n "[$1] $2"
    i=0                                                              # intialize iterator
    export RAND=$(head -c 5 /dev/urandom | hexdump -ve '1/1 "%.2x"') # creating a random index to label the pods and avoid name collision for repeated runs
    
    if [[ "$6" == "" ]]; then
        MSG="pod/pod-$1-${RAND} created"
    else
        MSG=$(envsubst <<<"$6")                                          # in case RAND is to be used, it needs to be added as ${RAND} to cases.yaml (and maybe deployment file)
    fi

    while :; do
        i=$((i + 1))
        if [[ "$3" == "deploy" ]]; then
            kubectl run pod-$1-${RAND} --image="$4" --namespace="$5" -luse="connaisseur-integration-test" >output.log 2>&1 || true
        elif [[ "$3" == "debug" ]]; then
            kubectl run $1-base-pod-${RAND} --image="securesystemsengineering/testimage:signed" --namespace="$5" -luse="connaisseur-integration-test" >/dev/null 2>&1 || true
            # Await base pod readiness as otherwise there may be multiple admission requests during the deployment of the ephemeral container
            kubectl wait --for=condition=Ready pod $1-base-pod-${RAND} --namespace="$5" >/dev/null 2>&1 || true
            kubectl debug $1-base-pod-${RAND} --image="$4" --namespace="$5" >output.log 2>&1 || true
        elif [[ "$3" == "workload" ]]; then
            envsubst <test/integration/workload/$4.yaml | kubectl apply -f - >output.log 2>&1 || true
        else
            kubectl apply -f "$4" >output.log 2>&1 || true
        fi
        # if the webhook couldn't be called, try again.
        [[ ("$(cat output.log)" =~ "failed calling webhook") && $i -lt ${RETRY} ]] || break
    done
    if [[ ! "$(cat output.log)" =~ "${MSG}" ]]; then
        echo -e ${FAILED}
        echo "::group::Output"
        cat output.log
        kubectl logs -n connaisseur -lapp.kubernetes.io/instance=connaisseur
        echo "::endgroup::"
        EXIT="1"
    else
        echo -e "${SUCCESS}"
    fi
    rm output.log

    if [[ "$7" != "null" ]]; then
        DEPLOYMENT_RES[$7]=$((${DEPLOYMENT_RES[$7]} + 1))
    fi

    # 3 tries on first test, 2 tries on second, 1 try for all subsequential
    RETRY=$((RETRY - 1))
}

multi_test() { # $1: file name relative to test/integration path

    # converting to json, as yq processing is pretty slow
    test_cases=$(yq e -o=json "." "${SCRIPT_PATH}"/$1)
    len=$(echo ${test_cases} | jq 'length')
    for i in $(seq 0 $(($len - 1))); do
        test_case=$(echo "${test_cases}" | jq ".[$i]")
        ID=$(echo "${test_case}" | jq -r ".id" | null_to_empty)
        ID=$(printf "%s-%02d-%s" "$(dirname $1)" "$((i+1))" "${ID:=unknown}")
        TEST_CASE_TXT=$(echo "${test_case}" | jq -r ".txt" | null_to_empty)
        TYPE=$(echo "${test_case}" | jq -r ".type" | null_to_empty)
        REF=$(echo "${test_case}" | jq -r ".ref" | null_to_empty)
        NAMESPACE=$(echo "${test_case}" | jq -r ".namespace" | null_to_empty)
        EXP_MSG=$(echo "${test_case}" | jq -r ".expected_msg" | null_to_empty)
        EXP_RES=$(echo "${test_case}" | jq -r ".expected_result" | null_to_empty)
        single_test "${ID}" "${TEST_CASE_TXT}" "${TYPE:=deploy}" "${REF}" "${NAMESPACE:=default}" "${EXP_MSG}" "${EXP_RES:=null}"
    done
}

test_case() { # $1: install.yaml, $2: cases.yaml, $3: install method, $4: uninstall method (defaults to $3)
    update_with_file "$1"
    install "$3"
    multi_test "$2"
    uninstall "${4:-$3}"
}
