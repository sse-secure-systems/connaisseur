#!/usr/bin/expect

spawn notary addhash docker.io/securesystemsengineering/testimage self-hosted-notary-signed 528 --sha256 [lindex $argv 0] --publish -c ./test/integration/self-hosted-notary/notary-service-container/client_config.json -s https://notary.server:4443 -D
expect "Enter passphrase for targets key with ID*\r"
send -- "0123456789\r"
expect "Enter passphrase for snapshot key with ID*\r"
send -- "0123456789\r"
expect eof