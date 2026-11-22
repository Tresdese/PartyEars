from .base import *
from .base import INSTALLED_APPS, database
import os

# party's token check and error format instead of a copy: both services trust auth's key and
# answer with contract 1.4.
from .party import JWT_CLAVE_PUBLICA, REST_FRAMEWORK
# party's channel layer instead of one of its own: for the MVP the queue events reach the
# clients through party's WebSocket (contract 7.1). It needs REDIS_URL; in memory, each
# process has its own layer and the events never leave queue.
from .party import CHANNEL_LAYERS

INSTALLED_APPS = INSTALLED_APPS + ['apps.musicqueue', 'apps.mensajeria']

DATABASES = database('queue')

PARTY_URL = os.environ.get('PARTY_URL', 'http://127.0.0.1:8003')

SERVICIO = 'queue'
OUTBOX_MODELO = 'musicqueue.EventoSalida'
RABBITMQ_EXCHANGE = 'queue.eventos'
RABBITMQ_URL = os.environ.get('QUEUE_RABBITMQ_URL', '')
REGISTRAR_RECHAZO = 'apps.musicqueue.servicios.registrar_rechazo'
