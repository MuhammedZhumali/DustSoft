#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$APP_DIR"

export DUSTSOFT_HARDWARE="${DUSTSOFT_HARDWARE:-raspberry-pi}"

if [[ -x "$APP_DIR/.venv/bin/python" ]]; then
  exec "$APP_DIR/.venv/bin/python" "$APP_DIR/src/main.py" gui
fi

if [[ -x "$APP_DIR/../.venv/bin/python" ]]; then
  exec "$APP_DIR/../.venv/bin/python" "$APP_DIR/src/main.py" gui
fi

exec python3 "$APP_DIR/src/main.py" gui
