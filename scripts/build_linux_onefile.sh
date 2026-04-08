#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if [[ ! -x .venv/bin/python ]]; then
  echo "Missing .venv. Run: python3 bootstrap.py install"
  exit 1
fi

.venv/bin/python -m pip install pyinstaller
.venv/bin/python -m PyInstaller \
  --noconfirm \
  --clean \
  --onefile \
  --name FreqFinder \
  --add-data "media:media" \
  --add-data "csv_files:csv_files" \
  --add-data "radioref.csv:." \
  freqfinder.py

echo "Built: dist/FreqFinder"
