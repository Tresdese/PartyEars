param(
    [Parameter(Mandatory)]
    [ValidateSet('auth', 'music', 'party', 'queue', 'streaming', 'logs')]
    [string]$Servicio
)

$ErrorActionPreference = 'Stop'
Set-Location -Path $PSScriptRoot
$puertos = @{ auth = 8001; music = 8002; party = 8003; queue = 8004; streaming = 8005; logs = 8006 }

if (-not (Test-Path .venv)) {
    python -m venv .venv
}
.\.venv\Scripts\python.exe -m pip install -q -r requirements.txt
# Checking the exit code instead of relying on ErrorActionPreference: it ignores native commands.
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

# Migrations by hand instead of on every start: the dev database is shared, so a branch's
# unmerged migrations would reach everyone (README section 6).
# 0.0.0.0 instead of 127.0.0.1: phones and other PCs on the network must reach the service.
$env:DJANGO_SETTINGS_MODULE = "config.settings.$Servicio"
.\.venv\Scripts\python.exe manage.py runserver "0.0.0.0:$($puertos[$Servicio])"
