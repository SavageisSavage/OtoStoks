#!/usr/bin/env bash
# OtoStoksBot Linux Launcher
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

echo "=========================================================="
echo "          Starting OtoStoksBot for Linux"
echo "=========================================================="

if command -v python3 &>/dev/null; then
    PY_BIN=python3
elif command -v python &>/dev/null; then
    PY_BIN=python
else
    echo "[!] Python 3 is required. Please install python3."
    exit 1
fi

if [ ! -d ".venv" ]; then
    echo "[*] Setting up Python virtual environment..."
    $PY_BIN -m venv .venv || true
fi

if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
    PY_BIN=python
fi

echo "[*] Verifying requirements..."
pip install -r requirements.txt --quiet --no-warn-script-location 2>/dev/null || true

echo "[*] Starting OtoStoksBot..."
$PY_BIN main.py
