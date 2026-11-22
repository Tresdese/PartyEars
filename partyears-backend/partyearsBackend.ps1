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
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$env:DJANGO_SETTINGS_MODULE = "config.settings.$Servicio"
.\.venv\Scripts\python.exe manage.py runserver "0.0.0.0:$($puertos[$Servicio])"
