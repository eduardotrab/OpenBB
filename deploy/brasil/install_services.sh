#!/usr/bin/env bash
# Install the OpenBB API and MCP as systemd *user* services for this project.
# Usage: openbb/deploy/brasil/install_services.sh   (from anywhere)
set -euo pipefail

# Project dir = parent of the fork checkout (holds openbb.toml).
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
UNIT_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"

for bin in openbb-api openbb-mcp; do
  [ -x "$PROJECT_DIR/openbb/.venv/bin/$bin" ] || { echo "missing $PROJECT_DIR/openbb/.venv/bin/$bin (run openbb/deploy/brasil/deploy.sh first)" >&2; exit 1; }
done

mkdir -p "$UNIT_DIR"
for unit in openbb-api openbb-mcp; do
  sed "s|@PROJECT_DIR@|$PROJECT_DIR|g" "$PROJECT_DIR/openbb/deploy/brasil/systemd/$unit.service" > "$UNIT_DIR/$unit.service"
  echo "installed $UNIT_DIR/$unit.service"
done

systemctl --user daemon-reload
systemctl --user enable --now openbb-api.service openbb-mcp.service
systemctl --user --no-pager --lines=0 status openbb-api.service openbb-mcp.service || true
echo "Logs: journalctl --user -u openbb-api -f"
