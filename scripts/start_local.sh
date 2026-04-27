#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

source .venv/bin/activate
echo "Installing dependencies..."
pip install -r requirements.txt -c constraints.txt --quiet

echo ""
echo "Starting arXiv Recommender at http://localhost:5555"
echo "Press Ctrl+C to stop."
echo ""

python web_server.py
