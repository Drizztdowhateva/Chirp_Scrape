#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "This script must run on macOS to create .app/.dmg"
  exit 1
fi

if [[ ! -x .venv/bin/python ]]; then
  echo "Missing .venv. Run: python3 bootstrap.py install"
  exit 1
fi

.venv/bin/python -m pip install pyinstaller
.venv/bin/python -m PyInstaller \
  --noconfirm \
  --clean \
  --windowed \
  --name FreqFinder \
  --add-data "media:media" \
  --add-data "csv_files:csv_files" \
  --add-data "radioref.csv:." \
  chirp_scraper.py

APP_PATH="dist/FreqFinder.app"
DMG_PATH="dist/FreqFinder.dmg"

if [[ ! -d "$APP_PATH" ]]; then
  echo "Expected app not found at $APP_PATH"
  exit 1
fi

hdiutil create -volname "FreqFinder" -srcfolder "$APP_PATH" -ov -format UDZO "$DMG_PATH"
echo "Built: $APP_PATH"
echo "Built: $DMG_PATH"
