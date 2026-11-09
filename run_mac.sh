#!/usr/bin/env bash
# OtoStoksBot macOS App Bundle Launcher
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

if [ -d "../Resources" ] && [ -f "../Resources/main.py" ]; then
    cd "../Resources"
fi

echo "=========================================================="
echo "          Starting OtoStoksBot for macOS"
echo "=========================================================="

if command -v python3 &>/dev/null; then
    PY_BIN=python3
elif command -v python &>/dev/null; then
    PY_BIN=python
else
    echo "[!] Python 3 is required. Please install python3 (e.g. brew install python)."
    exit 1
fi

if [ ! -d ".venv" ]; then
    echo "[*] Initializing local virtual environment..."
    $PY_BIN -m venv .venv || true
fi

if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
    PY_BIN=python
fi

echo "[*] Checking runtime dependencies..."
pip install -r requirements.txt --quiet --no-warn-script-location 2>/dev/null || true

echo "[*] Launching OtoStoksBot Native GUI..."
$PY_BIN main.py
