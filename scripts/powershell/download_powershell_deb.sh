#!/usr/bin/env bash
set -euo pipefail

# Download PowerShell Debian package on demand instead of committing it to git.
VERSION="${1:-7.5.4}"
OUT_DIR="${2:-scripts/powershell}"
FILE="powershell_${VERSION}-1.deb_amd64.deb"
URL="https://github.com/PowerShell/PowerShell/releases/download/v${VERSION}/${FILE}"

mkdir -p "$OUT_DIR"
OUT_PATH="$OUT_DIR/$FILE"

echo "Downloading $URL"
if command -v wget >/dev/null 2>&1; then
  wget -O "$OUT_PATH" "$URL"
elif command -v curl >/dev/null 2>&1; then
  curl -L "$URL" -o "$OUT_PATH"
else
  echo "Error: neither wget nor curl is installed." >&2
  exit 1
fi

echo "Saved: $OUT_PATH"
