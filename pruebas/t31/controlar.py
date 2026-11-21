"""Hace de anfitrión en la prueba de T-31: publica reproduccion.estado a la party.

Se corre desde partyears-backend con el venv y REDIS_URL (ver README.md):
    python ../pruebas/t31/controlar.py token
    python ../pruebas/t31/controlar.py iniciar | pausar | reanudar | buscar <ms>
"""
import json
import os
import sys
import time
import uuid
from pathlib import Path

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.party')
sys.path.insert(0, os.getcwd())

import django  # noqa: E402

django.setup()

import jwt  # noqa: E402
from asgiref.sync import async_to_sync  # noqa: E402
from django.conf import settings  # noqa: E402

from apps.parties.eventos import publicar  # noqa: E402

PARTY_ID = '11111111-1111-1111-1111-111111111111'
# Start a little in the future so every client receives the message before the start instant.
ARRANQUE_MS = 1500
ARCHIVO_ESTADO = Path(__file__).with_name('estado.json')


def ahora_ms():
    return time.time_ns() // 1_000_000


def iso(ms):
    return time.strftime('%Y-%m-%dT%H:%M:%S', time.gmtime(ms / 1000)) + f'.{ms % 1000:03d}Z'


def token():
    privada = (settings.BASE_DIR / 'claves-dev' / 'privada.pem').read_text()
    datos = {'sub': str(uuid.uuid4()), 'sid': str(uuid.uuid4()), 'exp': int(time.time()) + 4 * 3600}
    return jwt.encode(datos, privada, algorithm='RS256')


def leer_estado():
    if ARCHIVO_ESTADO.exists():
        return json.loads(ARCHIVO_ESTADO.read_text())
    return {'version': 0, 'estado': 'detenida', 'posicion_base_ms': 0, 'referencia_ms': ahora_ms()}


def posicion_actual(estado):
    if estado['estado'] == 'reproduciendo':
        return estado['posicion_base_ms'] + max(ahora_ms() - estado['referencia_ms'], 0)
    return estado['posicion_base_ms']


def main():
    accion = sys.argv[1] if len(sys.argv) > 1 else ''
    if accion == 'token':
        print(token())
        return

    estado = leer_estado()
    ahora = ahora_ms()
    if accion == 'iniciar':
        estado.update(estado='reproduciendo', posicion_base_ms=0, referencia_ms=ahora + ARRANQUE_MS)
    elif accion == 'pausar':
        estado.update(estado='pausada', posicion_base_ms=posicion_actual(estado), referencia_ms=ahora)
    elif accion == 'reanudar':
        estado.update(estado='reproduciendo', referencia_ms=ahora + ARRANQUE_MS)
    elif accion == 'buscar' and len(sys.argv) == 3:
        estado.update(posicion_base_ms=int(sys.argv[2]), referencia_ms=ahora + ARRANQUE_MS)
    else:
        sys.exit(__doc__)

    estado['version'] += 1
    ARCHIVO_ESTADO.write_text(json.dumps(estado))
    datos = {
        'cola_id': PARTY_ID,
        'version': estado['version'],
        'elemento_id': PARTY_ID,
        'recurso_audio_id': PARTY_ID,
        'estado': estado['estado'],
        'posicion_base_ms': estado['posicion_base_ms'],
        'referencia_en': iso(estado['referencia_ms']),
        'duracion_ms': None,
    }
    async_to_sync(publicar)(PARTY_ID, 'reproduccion.estado', datos, estado['version'])
    print(f'{accion}: {datos["estado"]} desde {datos["posicion_base_ms"]} ms, versión {estado["version"]}')


if __name__ == '__main__':
    main()
