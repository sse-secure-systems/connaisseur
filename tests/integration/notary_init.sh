#!/usr/bin/expect

spawn notary init docker.io/securesystemsengineering/testimage --publish -c ./tests/data/notary_service_container/config/client_config.json -s https://notary:4443
expect "Enter passphrase for targets key with ID*\r"
send -- "0123456789\r"
expect "Enter passphrase for snapshot key with ID*\r"
send -- "0123456789\r"
expect eof
