#!/bin/sh
set -euo pipefail

# Update packages and remove apk
apk update --no-cache && apk upgrade --no-cache && apk del apk-tools --no-cache && rm -rf /var/cache/apk

# Remove user accounts
echo "" > /etc/group
echo "" > /etc/passwd
echo "" > /etc/shadow

# Remove crons
rm -fr /var/spool/cron
rm -fr /etc/crontabs
rm -fr /etc/periodic

# Remove init scripts
rm -fr /etc/init.d
rm -fr /etc/conf.d
rm -f /etc/inittab

# Remove media stuff
rm -f /etc/fstab
rm -fr /media
