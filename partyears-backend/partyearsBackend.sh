#!/usr/bin/env bash
set -e

# Ir al directorio donde se encuentra este script (partyears-backend)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Permitir pasar el servicio como argumento (auth, music, party, queue, streaming, logs)
# Por defecto levanta config.settings.base
SERVICE_SETTINGS="${1:-config.settings.base}"
PORT="${2:-8000}"

echo "=== Iniciando entorno PartyEars Backend ($SERVICE_SETTINGS) ==="

# 1. Crear entorno virtual si no existe
if [ ! -d ".venv" ]; then
    echo "Creando entorno virtual en .venv..."
    python3 -m venv .venv
fi

# 2. Activar entorno virtual
source .venv/bin/activate

# 3. Instalar/actualizar dependencias
echo "Verificando dependencias de requirements.txt..."
pip install --upgrade pip -q
pip install -r requirements.txt

# 4. Cargar variables de entorno desde .env si existe
if [ -f ".env" ]; then
    set -a
    source .env
    set +a
fi

# 5. Ejecutar migraciones y levantar el servidor
echo "Ejecutando migraciones..."
python manage.py migrate --settings="$SERVICE_SETTINGS"

echo "Servidor corriendo en http://0.0.0.0:$PORT"
python manage.py runserver "0.0.0.0:$PORT" --settings="$SERVICE_SETTINGS"