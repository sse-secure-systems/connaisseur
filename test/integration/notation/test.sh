#!/usr/bin/env bash
set -euo pipefail

notation_test() {
    update_with_file "notation/install.yaml"
    install "make"
    multi_test "notation/cases.yaml"
    uninstall "make"
}
