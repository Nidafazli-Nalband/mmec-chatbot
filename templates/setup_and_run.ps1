# setup_and_run.ps1
# Creates a virtual environment, installs requirements and runs server.py
# Run from PowerShell (Windows) in the template folder

$ErrorActionPreference = 'Stop'
$cwd = Split-Path -Path $MyInvocation.MyCommand.Definition -Parent
Write-Host "Working directory: $cwd"
Set-Location $cwd

# Create venv
if (-not (Test-Path ".venv")) {
    Write-Host "Creating virtual environment .venv..."
    python -m venv .venv
}

# Activate
Write-Host "Activating virtual environment..."
. .\.venv\Scripts\Activate.ps1

# Upgrade pip
Write-Host "Upgrading pip..."
python -m pip install --upgrade pip setuptools wheel

# Install requirements
if (Test-Path "requirements.txt") {
    Write-Host "Installing requirements from requirements.txt..."
    pip install -r requirements.txt
} else {
    Write-Host "requirements.txt not found; skipping install"
}

# Run server
Write-Host "Starting Flask server (server.py)..."
python server.py
