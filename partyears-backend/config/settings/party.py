from .base import *
from .base import INSTALLED_APPS, database
import os

INSTALLED_APPS = INSTALLED_APPS + ['apps.parties']

DATABASES = database('party')

WS_TIEMPO_AUTENTICAR = 5

JWT_CLAVE_PUBLICA = os.environ.get('JWT_CLAVE_PUBLICA', '')

if os.environ.get('REDIS_URL'):
    CHANNEL_LAYERS = {'default': {'BACKEND': 'channels_redis.core.RedisChannelLayer',
                                  'CONFIG': {'hosts': [os.environ['REDIS_URL']]}}}
else:
    CHANNEL_LAYERS = {'default': {'BACKEND': 'channels.layers.InMemoryChannelLayer'}}