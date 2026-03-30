#!/usr/bin/env bash
set -euo pipefail

# Remote SSH helper for ChirpScrape local dev build/run
# Usage:
#   ./scripts/rssh-run.sh user@host /path/to/Chirp_Scrape

if [ "$#" -ne 2 ]; then
  echo "Usage: $0 user@host /path/to/Chirp_Scrape"
  exit 1
fi

REMOTE="$1"
REMOTE_PATH="$2"

ssh "$REMOTE" "set -euo pipefail; cd '$REMOTE_PATH'; if [ -f gradlew ]; then chmod +x gradlew; ./gradlew --no-daemon --stacktrace --info clean build; else echo 'gradlew not found in remote project path'; fi"
