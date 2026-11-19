from .base import *
from .base import INSTALLED_APPS, database
import os

INSTALLED_APPS = ['daphne'] + INSTALLED_APPS + ['channels', 'apps.parties']

ASGI_APPLICATION = 'config.asgi.application'

DATABASES = database('party')

WS_TIEMPO_AUTENTICAR = 5

JWT_CLAVE_PUBLICA = os.environ.get('JWT_CLAVE_PUBLICA', '')

if os.environ.get('REDIS_URL'):
    CHANNEL_LAYERS = {'default': {'BACKEND': 'channels_redis.core.RedisChannelLayer',
                                  'CONFIG': {'hosts': [os.environ['REDIS_URL']]}}}
else:
    CHANNEL_LAYERS = {'default': {'BACKEND': 'channels.layers.InMemoryChannelLayer'}}