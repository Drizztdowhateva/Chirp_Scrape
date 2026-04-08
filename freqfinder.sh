#!/usr/bin/env bash
set -euo pipefail

# Run FreqFinder from the repository root.
# If needed, this script creates a local virtualenv and installs dependencies.

cd "$(dirname "$0")"

if [[ ! -d .venv ]]; then
  echo "Creating Python virtual environment in .venv..."
  python3 -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate

PYTHON_EXE="$(pwd)/.venv/bin/python"
PIP_EXE="$(pwd)/.venv/bin/python -m pip"

if [[ ! -f requirements.txt ]]; then
  echo "Missing requirements.txt" >&2
  exit 1
fi

"$PYTHON_EXE" -m pip install --upgrade pip
"$PYTHON_EXE" -m pip install --break-system-packages -r requirements.txt

# Launch FreqFinder with any extra args passed through
"$PYTHON_EXE" freqfinder.py "$@"
