#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

SERVICE_SETTINGS="${1:-config.settings.base}"
PORT="${2:-8000}"

echo "=== Iniciando entorno PartyEars Backend ($SERVICE_SETTINGS) ==="


if [ ! -d ".venv" ]; then
    echo "Creando entorno virtual en .venv..."
    python3 -m venv .venv
fi


source .venv/bin/activate


echo "Verificando dependencias de requirements.txt..."
pip install --upgrade pip -q
pip install -r requirements.txt


if [ -f ".env" ]; then
    set -a
    source .env
    set +a
fi


echo "Ejecutando migraciones..."
python manage.py migrate --settings="$SERVICE_SETTINGS"

echo "Servidor corriendo en http://0.0.0.0:$PORT"
python manage.py runserver "0.0.0.0:$PORT" --settings="$SERVICE_SETTINGS"