from .base import *
from .base import BASE_DIR, INSTALLED_APPS, database
from datetime import timedelta
import os

INSTALLED_APPS = ['daphne'] + INSTALLED_APPS + ['channels', 'apps.parties', 'apps.mensajeria']

ASGI_APPLICATION = 'config.asgi.application'

DATABASES = database('party')

WS_TIEMPO_AUTENTICAR = 5

WS_TIEMPO_SIN_LATIDO = 15

PARTY_VIGENCIA_CODIGO = timedelta(hours=24)

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': ['apps.parties.autenticacion.JWTAuthentication'],
    'DEFAULT_PERMISSION_CLASSES': ['rest_framework.permissions.IsAuthenticated'],
    'DEFAULT_RENDERER_CLASSES': ['rest_framework.renderers.JSONRenderer'],
    'DEFAULT_PARSER_CLASSES': ['rest_framework.parsers.JSONParser'],
    'EXCEPTION_HANDLER': 'apps.parties.errores.manejar_excepcion',
    'UNAUTHENTICATED_USER': None,
}

# Path instead of the key itself: a PEM spans several lines and the .env loader
# reads one line per variable. Relative paths resolve against partyears-backend.
JWT_CLAVE_PUBLICA = ((BASE_DIR / os.environ['JWT_CLAVE_PUBLICA_ARCHIVO']).read_text()
                     if os.environ.get('JWT_CLAVE_PUBLICA_ARCHIVO') else '')

if os.environ.get('REDIS_URL'):
    # redis-py 8 defaults socket_timeout to 5 s, the same as channels_redis' blocking read
    # (BZPOPMIN, 5 s): every idle party dropped its WebSockets. The timeout must exceed it.
    CHANNEL_LAYERS = {'default': {'BACKEND': 'channels_redis.core.RedisChannelLayer',
                                  'CONFIG': {'hosts': [{'address': os.environ['REDIS_URL'],
                                                        'socket_timeout': 15}]}}}
else:
    CHANNEL_LAYERS = {'default': {'BACKEND': 'channels.layers.InMemoryChannelLayer'}}

# Events between services (DECISIONES.md): publicar_eventos sends the outbox to party.eventos.
SERVICIO = 'party'
OUTBOX_MODELO = 'parties.EventoSalida'
RABBITMQ_EXCHANGE = 'party.eventos'
RABBITMQ_URL = os.environ.get('PARTY_RABBITMQ_URL', '')
REGISTRAR_RECHAZO = 'apps.parties.servicios.registrar_rechazo'
