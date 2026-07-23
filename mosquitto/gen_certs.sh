#!/usr/bin/env bash
# Genera certificados TLS autofirmados para desarrollo (CA + servidor).
# Uso:  bash mosquitto/gen_certs.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CERTS="$ROOT/certs"
mkdir -p "$CERTS"
cd "$CERTS"

CN="${MQTT_CN:-localhost}"

echo "==> CA"
openssl genrsa -out ca.key 2048
openssl req -new -x509 -days 3650 -key ca.key -out ca.crt \
  -subj "/C=AR/ST=Mendoza/O=VitisGuard/CN=VitisGuard-CA"

echo "==> Servidor (CN=$CN)"
openssl genrsa -out server.key 2048
openssl req -new -key server.key -out server.csr \
  -subj "/C=AR/ST=Mendoza/O=VitisGuard/CN=$CN"

# SAN para que valide 'localhost' e IP local
cat > san.ext <<EOF
subjectAltName = DNS:$CN, DNS:localhost, IP:127.0.0.1
EOF

openssl x509 -req -in server.csr -CA ca.crt -CAkey ca.key -CAcreateserial \
  -out server.crt -days 3650 -sha256 -extfile san.ext

rm -f server.csr san.ext
echo "==> Listo. Certificados en $CERTS"
ls -1 "$CERTS"
