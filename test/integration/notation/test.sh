#!/usr/bin/env bash
set -euo pipefail

notation_test() {
    update_with_file "notation/install.yaml"
    update '(.application.validators[] | select(.name == "ghcr-notation") | .auth) += {"secretName": env(IMAGEPULLSECRET)}'
    install "make"
    multi_test "notation/cases.yaml"
    uninstall "make"
}
