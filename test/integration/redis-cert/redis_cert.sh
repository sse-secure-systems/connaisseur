#!/usr/bin/env bash
set -euo pipefail

redis_cert_test() {
    echo "Running redis-cert test"
    update_with_file "redis-cert/install.yaml"
    make_install
    update_with_file "redis-cert/update.yaml"
    make_upgrade
}
