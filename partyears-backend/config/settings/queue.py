from .base import *
from .base import INSTALLED_APPS, database
import os

# party's token check and error format instead of a copy: both services trust auth's key and
# answer with contract 1.4.
from .party import JWT_CLAVE_PUBLICA, REST_FRAMEWORK

INSTALLED_APPS = INSTALLED_APPS + ['apps.musicqueue']

DATABASES = database('queue')

PARTY_URL = os.environ.get('PARTY_URL', 'http://127.0.0.1:8003')
