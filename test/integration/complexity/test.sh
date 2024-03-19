#!/usr/bin/env bash
set -euo pipefail

complexity_test() {
    update_with_file "complexity/install.yaml"
    install "make"
    time create_complexity
    uninstall "make"
}

create_complexity() {
    echo -n 'Testing Connaisseur with complex requests...'
    kubectl apply -f test/integration/complexity/complex_deployment.yaml >output.log 2>&1 || true
    if [[ ! ("$(cat output.log)" =~ 'deployment.apps/redis-with-many-instances created' && "$(cat output.log)" =~ 'pod/pod-with-many-containers created' && "$(cat output.log)" =~ 'pod/pod-with-many-containers-and-init-containers created' && "$(cat output.log)" =~ 'pod/pod-with-some-containers-and-init-containers created' && "$(cat output.log)" =~ 'pod/pod-with-coinciding-containers-and-init-containers created') ]]; then
        echo -e ${FAILED}
        echo "::group::Output"
        cat output.log
        echo "::endgroup::"
        EXIT="1"
    else
        echo -e "${SUCCESS}"
    fi
    rm output.log
}
