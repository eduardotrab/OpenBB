#!/usr/bin/env bash
# Install (or update) OpenBB with the Brazilian providers from scratch.
#
# Usage:
#   curl -fsSLO https://raw.githubusercontent.com/eduardotrab/openbb/feature/brazil-providers/deploy/brasil/deploy.sh
#   bash deploy.sh [PROJECT_DIR] [--no-services]
#
# PROJECT_DIR (default: ~/openbb-brasil) receives:
#   openbb/        the fork checkout (branch $OPENBB_BRANCH)
#   openbb.toml    runtime config (ports 6900/6901, news feeds) - kept if it exists
# Requirements: git, python3 >= 3.10, and uv (installed with pipx if missing).
set -euo pipefail

REPO_URL="${OPENBB_REPO_URL:-https://github.com/eduardotrab/openbb}"
BRANCH="${OPENBB_BRANCH:-feature/brazil-providers}"
PROJECT_DIR="$HOME/openbb-brasil"
INSTALL_SERVICES=1
for arg in "$@"; do
  case "$arg" in
    --no-services) INSTALL_SERVICES=0 ;;
    *) PROJECT_DIR="$arg" ;;
  esac
done

step() { printf '\n==> %s\n' "$*"; }

step "Checking requirements"
command -v git >/dev/null || { echo "git is required (sudo apt install git)" >&2; exit 1; }
python3 -c 'import sys; sys.exit(sys.version_info < (3, 10))' \
  || { echo "python3 >= 3.10 is required" >&2; exit 1; }
export PATH="$HOME/.local/bin:$PATH"
if ! command -v uv >/dev/null; then
  command -v pipx >/dev/null || { echo "uv or pipx is required (sudo apt install pipx)" >&2; exit 1; }
  pipx install uv
fi
uv --version

step "Fetching $REPO_URL ($BRANCH) into $PROJECT_DIR/openbb"
mkdir -p "$PROJECT_DIR"
if [ -d "$PROJECT_DIR/openbb/.git" ]; then
  git -C "$PROJECT_DIR/openbb" fetch origin "$BRANCH"
  git -C "$PROJECT_DIR/openbb" checkout "$BRANCH"
  git -C "$PROJECT_DIR/openbb" merge --ff-only "origin/$BRANCH"
else
  git clone --branch "$BRANCH" "$REPO_URL" "$PROJECT_DIR/openbb"
fi

step "Creating the virtual environment"
[ -x "$PROJECT_DIR/openbb/.venv/bin/python" ] || uv venv --python python3 "$PROJECT_DIR/openbb/.venv"

step "Installing OpenBB and providers (takes ~15 minutes the first time)"
VIRTUAL_ENV="$PROJECT_DIR/openbb/.venv" \
  "$PROJECT_DIR/openbb/.venv/bin/python" "$PROJECT_DIR/openbb/deploy/brasil/install_openbb.py" --routers

step "Runtime config"
if [ -f "$PROJECT_DIR/openbb.toml" ]; then
  echo "keeping existing $PROJECT_DIR/openbb.toml"
else
  cp "$PROJECT_DIR/openbb/deploy/brasil/openbb.toml" "$PROJECT_DIR/openbb.toml"
  echo "created $PROJECT_DIR/openbb.toml"
fi

step "Smoke test"
(cd "$PROJECT_DIR" && openbb/.venv/bin/python -c \
  "from openbb import obb; p = obb.coverage.providers; missing = {'bcb','ibge','tesouro','cvm','receita'} - set(p); assert not missing, missing; print('providers ok:', sorted(p))")

if [ "$INSTALL_SERVICES" = 1 ]; then
  step "Installing systemd user services"
  "$PROJECT_DIR/openbb/deploy/brasil/install_services.sh"
fi

step "Done. API: http://127.0.0.1:6900/docs  MCP: http://127.0.0.1:6901/mcp"
