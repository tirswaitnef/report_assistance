#!/usr/bin/env bash
set -euo pipefail

# A local-only, self-signed certificate is sufficient for testing whether the
# server permits/requires TLS. This is not a production trust configuration.
install -d -m 0700 -o postgres -g postgres /tmp/lab-tls
if [[ ! -s /tmp/lab-tls/server.key || ! -s /tmp/lab-tls/server.crt ]]; then
    openssl req -x509 -newkey rsa:2048 -sha256 -nodes -days 30 \
        -subj '/CN=pg-b' \
        -addext 'subjectAltName=DNS:pg-b,DNS:localhost,IP:127.0.0.1' \
        -keyout /tmp/lab-tls/server.key \
        -out /tmp/lab-tls/server.crt >/dev/null 2>&1
fi
chown postgres:postgres /tmp/lab-tls/server.key /tmp/lab-tls/server.crt
chmod 0600 /tmp/lab-tls/server.key
chmod 0644 /tmp/lab-tls/server.crt

exec /usr/local/bin/docker-entrypoint.sh "$@"
