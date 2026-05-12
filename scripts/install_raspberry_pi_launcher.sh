#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LAUNCHER="$APP_DIR/dustsoft-gui.sh"
DESKTOP_DIR="${HOME}/Desktop"
DESKTOP_FILE="${DESKTOP_DIR}/DustSoft.desktop"

chmod +x "$LAUNCHER"
mkdir -p "$DESKTOP_DIR"

cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Type=Application
Name=DustSoft
Comment=DustSoft operator GUI
Exec=$LAUNCHER
Path=$APP_DIR
Terminal=false
Categories=Utility;
EOF

chmod +x "$DESKTOP_FILE"

if command -v gio >/dev/null 2>&1; then
  gio set "$DESKTOP_FILE" metadata::trusted true >/dev/null 2>&1 || true
fi

echo "Created desktop launcher: $DESKTOP_FILE"
