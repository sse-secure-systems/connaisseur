#!/usr/bin/env bash
set -euo pipefail

create_load() {
    NUMBER_OF_INSTANCES=100
    echo -n 'Testing Connaisseur with many requests...'
    parallel --jobs 20 test/integration/load/cause_load.sh {1} :::: <(seq ${NUMBER_OF_INSTANCES}) >output.log 2>&1 || true
    NUMBER_CREATED=$(cat output.log | grep "deployment[.]apps/redis-[0-9]* created" | wc -l || echo "0")
    if [[ ${NUMBER_CREATED} != "${NUMBER_OF_INSTANCES}" ]]; then
        echo -e ${FAILED}
        echo "::group::Output"
        echo "Only ${NUMBER_CREATED}/${NUMBER_OF_INSTANCES} pods were created."
        cat output.log
        echo "::endgroup::"
        EXIT="1"
    else
        echo -e "${SUCCESS}"
    fi
    rm output.log
}

load_test() {
    update_with_file "load/install.yaml"
    install "make"
    time create_load
    uninstall "make"
}
