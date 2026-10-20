#!/usr/bin/env bash
# Install the OpenBB API, MCP, the dashboard and the daily regional-data refresh
# as systemd *user* units for this project.
# Usage: [PAINEL_HOST=0.0.0.0] openbb/deploy/brasil/install_services.sh   (from anywhere)
#   PAINEL_HOST defaults to 127.0.0.1 (only this machine). Use 0.0.0.0 in production to
#   serve the dashboard to the cooperative network (open port 6902 in the firewall).
set -euo pipefail

# Project dir = parent of the fork checkout (holds openbb.toml).
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
UNIT_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
PAINEL_DIR="$HOME/.config/openbb-painel"
PAINEL_ENV="$PAINEL_DIR/painel.env"

for bin in openbb-api openbb-mcp gunicorn painel-usuarios painel-dados; do
  [ -x "$PROJECT_DIR/openbb/.venv/bin/$bin" ] || { echo "missing $PROJECT_DIR/openbb/.venv/bin/$bin (run openbb/deploy/brasil/deploy.sh first)" >&2; exit 1; }
done

# Dashboard config: secret key + self-signed certificate, created once and kept.
mkdir -p "$PAINEL_DIR" && chmod 700 "$PAINEL_DIR"
if [ ! -f "$PAINEL_DIR/tls/painel.crt" ]; then
  "$PROJECT_DIR/openbb/brasil_painel/scripts/gerar_certificado.sh" "$PAINEL_DIR/tls"
fi
if [ ! -f "$PAINEL_ENV" ]; then
  umask 077
  cat > "$PAINEL_ENV" <<CONF
# Dashboard settings (read by openbb-painel.service). Keep this file private (chmod 600).
PAINEL_SECRET_KEY=$(python3 -c 'import secrets; print(secrets.token_hex(32))')
PAINEL_HOST=${PAINEL_HOST:-127.0.0.1}
PAINEL_PORT=6902
PAINEL_USERS_FILE=$PAINEL_DIR/usuarios.json
PAINEL_CERTFILE=$PAINEL_DIR/tls/painel.crt
PAINEL_KEYFILE=$PAINEL_DIR/tls/painel.key
OPENBB_API_URL=http://127.0.0.1:6900/api/v1
CONF
  echo "created $PAINEL_ENV"
elif [ -n "${PAINEL_HOST:-}" ]; then
  sed -i "s|^PAINEL_HOST=.*|PAINEL_HOST=$PAINEL_HOST|" "$PAINEL_ENV"
  echo "PAINEL_HOST=$PAINEL_HOST set in $PAINEL_ENV"
fi

mkdir -p "$UNIT_DIR"
for unit in openbb-api.service openbb-mcp.service openbb-painel.service openbb-dados.service openbb-dados.timer; do
  sed "s|@PROJECT_DIR@|$PROJECT_DIR|g" "$PROJECT_DIR/openbb/deploy/brasil/systemd/$unit" > "$UNIT_DIR/$unit"
  echo "installed $UNIT_DIR/$unit"
done

systemctl --user daemon-reload
systemctl --user enable openbb-api.service openbb-mcp.service openbb-painel.service
systemctl --user restart openbb-api.service openbb-mcp.service openbb-painel.service
systemctl --user enable --now openbb-dados.timer
# First load of the regional data in the background (~1–2 min; the map waits for it).
systemctl --user start --no-block openbb-dados.service
systemctl --user --no-pager --lines=0 status openbb-api.service openbb-mcp.service openbb-painel.service || true
echo "Logs: journalctl --user -u openbb-api -f   |   journalctl --user -u openbb-painel -f   |   journalctl --user -u openbb-dados"
if [ -z "$(PAINEL_USERS_FILE="$PAINEL_DIR/usuarios.json" "$PROJECT_DIR/openbb/.venv/bin/painel-usuarios" list | grep -v '^(nenhum')" ]; then
  echo "No dashboard users yet: $PROJECT_DIR/openbb/.venv/bin/painel-usuarios add <usuario>"
fi
