param(
    [Parameter(Mandatory)]
    [ValidateSet('auth', 'music', 'party', 'queue', 'streaming', 'logs', 'todos')]
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
if ($Servicio -ne 'todos') {
    $env:DJANGO_SETTINGS_MODULE = "config.settings.$Servicio"
    .\.venv\Scripts\python.exe manage.py runserver "0.0.0.0:$($puertos[$Servicio])"
    exit $LASTEXITCODE
}

# todos: one window per process instead of one console, so each log stays readable; closing a
# window stops that process.
function Abrir([string]$titulo, [string]$settings, [string]$comando) {
    $orden = "`$Host.UI.RawUI.WindowTitle = 'PartyEars $titulo'; " +
             "`$env:DJANGO_SETTINGS_MODULE = 'config.settings.$settings'; " +
             ".\.venv\Scripts\python.exe manage.py $comando"
    Start-Process powershell -WorkingDirectory $PSScriptRoot -ArgumentList '-NoExit', '-Command', $orden
}

foreach ($s in 'auth', 'music', 'party', 'queue') {
    Abrir $s $s "runserver --noreload 0.0.0.0:$($puertos[$s])"
}

# Event workers only when their RabbitMQ URL is in .env: without them the party still works,
# the events wait in the outbox (README section 6.1).
$entorno = if (Test-Path .env) { Get-Content .env } else { @() }
function Tiene([string]$variable) { [bool]($entorno | Where-Object { $_ -match "^$variable=.+" }) }
if (Tiene 'PARTY_RABBITMQ_URL') { Abrir 'party-eventos' 'party' 'publicar_eventos' }
if (Tiene 'QUEUE_RABBITMQ_URL') { Abrir 'queue-eventos' 'queue' 'publicar_eventos' }
if (Tiene 'LOGS_RABBITMQ_URL') { Abrir 'logs-eventos' 'logs' 'consumir_eventos' }

Write-Host 'Backend corriendo: una ventana por servicio. Ciérralas para detenerlo.'
