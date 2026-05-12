#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

source .venv/bin/activate
echo "Installing dependencies..."
python -m pip install --upgrade pip setuptools wheel --quiet
python -m pip install -r requirements.txt -c constraints.txt --quiet

echo ""
echo "Starting Paper Agent at http://localhost:5555"
echo "Press Ctrl+C to stop."
echo ""

python web_server.py
