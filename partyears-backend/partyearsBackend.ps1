param(
    [string]$Settings = "config.settings.base",
    [string]$Port = "8000"
)

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

Write-Host "=== Iniciando entorno PartyEars Backend ($Settings) ===" -ForegroundColor Cyan

if (-not (Test-Path ".venv")) {
    Write-Host "Creando entorno virtual en .venv..."
    python -m venv .venv
}


& ".\.venv\Scripts\Activate.ps1"
python -m pip install --upgrade pip -q
pip install -r requirements.txt


if (Test-Path ".env") {
    Get-Content ".env" | ForEach-Object {
        if ($_ -match "^\s*([^#][^=]+)=(.*)$") {
            [System.Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim(), "Process")
        }
    }
}

python manage.py migrate --settings=$Settings
python manage.py runserver "127.0.0.1:$Port" --settings=$Settings