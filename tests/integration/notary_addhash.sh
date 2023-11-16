#!/usr/bin/expect

spawn notary addhash docker.io/securesystemsengineering/testimage self-hosted-notary-signed 528 --sha256 ${DIGEST_WITHOUT_PREFIX} --publish -c ./tests/data/notary_service_container/config/client_config.json -s https://notary:4443
expect "Enter passphrase for new root key with ID*\r"
send -- "0123456789\r"
expect "Repeat passphrase for new root key with ID*\r"
send -- "0123456789\r"
expect "Enter passphrase for new targets key with ID*\r"
send -- "0123456789\r"
expect "Repeat passphrase for new targets key with ID*\r"
send -- "0123456789\r"
expect "Enter passphrase for new snapshot key with ID*\r"
send -- "0123456789\r"
expect "Repeat passphrase for new snapshot key with ID*\r"
send -- "0123456789\r"
expect eof
