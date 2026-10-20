#!/usr/bin/env bash
# Generates a self-signed certificate for the dashboard (homologation).
# In production prefer a certificate issued by the cooperative's IT.
# Usage: gerar_certificado.sh [DIR] [HOSTNAME_OR_IP ...]
set -euo pipefail
DIR="${1:-$HOME/.config/openbb-painel/tls}"
shift || true
NAMES=("$(hostname)" "localhost" "$@")
SAN="IP:127.0.0.1"
for name in "${NAMES[@]}"; do
  if [[ "$name" =~ ^[0-9.]+$ ]]; then SAN+=",IP:$name"; else SAN+=",DNS:$name"; fi
done
for ip in $(hostname -I 2>/dev/null); do [[ "$ip" == *:* ]] || SAN+=",IP:$ip"; done
mkdir -p "$DIR" && chmod 700 "$DIR"
openssl req -x509 -newkey rsa:3072 -sha256 -days 825 -nodes \
  -keyout "$DIR/painel.key" -out "$DIR/painel.crt" \
  -subj "/CN=$(hostname)" -addext "subjectAltName=$SAN" 2>/dev/null
chmod 600 "$DIR/painel.key"
echo "Certificado: $DIR/painel.crt (SAN: $SAN)"
echo "Chave:       $DIR/painel.key"
