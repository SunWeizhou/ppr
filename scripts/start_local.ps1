$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $MyInvocation.MyCommand.Path)\..

if (-not (Test-Path ".venv")) {
    Write-Host "Creating virtual environment..."
    python -m venv .venv
}

.\.venv\Scripts\Activate.ps1
Write-Host "Installing dependencies..."
pip install -r requirements.txt -c constraints.txt --quiet

Write-Host ""
Write-Host "Starting arXiv Recommender at http://localhost:5555"
Write-Host "Press Ctrl+C to stop."
Write-Host ""

python web_server.py
