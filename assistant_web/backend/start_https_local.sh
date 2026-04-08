#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
CERT_DIR="$ROOT_DIR/certs"
CERT_FILE="$CERT_DIR/local-cert.pem"
KEY_FILE="$CERT_DIR/local-key.pem"
IP_ADDR="${1:-}"

if [[ -z "$IP_ADDR" ]]; then
  IP_ADDR="$(hostname -I | awk '{print $1}')"
fi

mkdir -p "$CERT_DIR"

if [[ ! -f "$CERT_FILE" || ! -f "$KEY_FILE" ]]; then
  TMP_CONF="$CERT_DIR/openssl-local.cnf"
  cat > "$TMP_CONF" <<EOF
[req]
default_bits = 2048
prompt = no
default_md = sha256
x509_extensions = v3_req
distinguished_name = dn

[dn]
C = KR
ST = Gyeonggi
L = Local
O = OmniMate
OU = LocalDev
CN = $IP_ADDR

[v3_req]
subjectAltName = @alt_names

[alt_names]
DNS.1 = localhost
IP.1 = 127.0.0.1
IP.2 = $IP_ADDR
EOF

  openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout "$KEY_FILE" \
    -out "$CERT_FILE" \
    -config "$TMP_CONF"
fi

export ASSISTANT_WEB_TLS_CERT="$CERT_FILE"
export ASSISTANT_WEB_TLS_KEY="$KEY_FILE"
export ASSISTANT_WEB_HOST="0.0.0.0"
export ASSISTANT_WEB_PORT="8443"

if command -v lsof >/dev/null 2>&1; then
  OLD_PIDS="$(lsof -ti tcp:8443 || true)"
  if [[ -n "$OLD_PIDS" ]]; then
    echo "Killing existing process on :8443 -> $OLD_PIDS"
    kill $OLD_PIDS || true
    sleep 1
  fi
fi

echo "HTTPS cert: $CERT_FILE"
echo "HTTPS key : $KEY_FILE"
echo "Open: https://localhost:8443"
echo "LAN : https://$IP_ADDR:8443"

/usr/bin/python3 "$ROOT_DIR/run_server.py"
