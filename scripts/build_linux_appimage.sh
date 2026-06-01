#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"/..

if [[ "$(uname -s)" != "Linux" ]]; then
  echo "This script must run on Linux to create an AppImage"
  exit 1
fi

if [[ ! -x .venv/bin/python ]]; then
  echo "Missing .venv. Run: python3 bootstrap.py install" >&2
  exit 1
fi

# Build the onefile executable first.
.venv/bin/python -m PyInstaller \
  --noconfirm \
  --clean \
  --onefile \
  --name FreqFinder \
  --add-data "media:media" \
  --add-data "csv_files:csv_files" \
  --add-data "radioref.csv:." \
  freqfinder.py

APPDIR="dist/FreqFinder.AppDir"
rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/bin"
mkdir -p "$APPDIR/usr/share/applications"
mkdir -p "$APPDIR/usr/share/icons/hicolor/256x256/apps"

cp dist/FreqFinder "$APPDIR/usr/bin/"

cat > "$APPDIR/FreqFinder.desktop" <<'EOF'
[Desktop Entry]
Name=FreqFinder
Exec=FreqFinder
Icon=freqfinder
Type=Application
Categories=Utility;Education;
EOF

if [[ -f "media/FreqFinder_20260504.png" ]]; then
  cp "media/FreqFinder_20260504.png" "$APPDIR/usr/share/icons/hicolor/256x256/apps/freqfinder.png"
fi

APPIMAGETOOL="./appimagetool-x86_64.AppImage"
if [[ ! -x "$APPIMAGETOOL" ]]; then
  echo "Downloading AppImage tool..."
  if command -v curl >/dev/null 2>&1; then
    curl -L -o "$APPIMAGETOOL" https://github.com/AppImage/AppImageKit/releases/latest/download/appimagetool-x86_64.AppImage
  elif command -v wget >/dev/null 2>&1; then
    wget -O "$APPIMAGETOOL" https://github.com/AppImage/AppImageKit/releases/latest/download/appimagetool-x86_64.AppImage
  else
    echo "curl or wget is required to download appimagetool" >&2
    exit 1
  fi
  chmod +x "$APPIMAGETOOL"
fi

"$APPIMAGETOOL" "$APPDIR" "dist/FreqFinder.AppImage"
chmod +x "dist/FreqFinder.AppImage"

echo "Built: dist/FreqFinder.AppImage"
