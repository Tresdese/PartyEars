$ActivateScript = ".\.venv\Scripts\Activate.ps1"

if (-not (Test-Path $ActivateScript)) {
    Write-Host "No existe el entorno virtual .venv."
    Write-Host "Créalo primero con: python -m venv .venv"
    return
}

. $ActivateScript