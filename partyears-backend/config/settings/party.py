from .base import *
from .base import BASE_DIR, INSTALLED_APPS, database
import os

INSTALLED_APPS = ['daphne'] + INSTALLED_APPS + ['channels', 'apps.parties']

ASGI_APPLICATION = 'config.asgi.application'

DATABASES = database('party')

WS_TIEMPO_AUTENTICAR = 5

# Path instead of the key itself: a PEM spans several lines and the .env loader
# reads one line per variable. Relative paths resolve against partyears-backend.
JWT_CLAVE_PUBLICA = ((BASE_DIR / os.environ['JWT_CLAVE_PUBLICA_ARCHIVO']).read_text()
                     if os.environ.get('JWT_CLAVE_PUBLICA_ARCHIVO') else '')

if os.environ.get('REDIS_URL'):
    CHANNEL_LAYERS = {'default': {'BACKEND': 'channels_redis.core.RedisChannelLayer',
                                  'CONFIG': {'hosts': [os.environ['REDIS_URL']]}}}
else:
    CHANNEL_LAYERS = {'default': {'BACKEND': 'channels.layers.InMemoryChannelLayer'}}