import json
import logging

import pika
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import DataError, IntegrityError

from apps.logs.registro import guardar
from apps.mensajeria.reintentos import FALLAS_RECUPERABLES, esperar_y_reintentar

logger = logging.getLogger(__name__)

COLAS = ('logs.desde_party', 'logs.desde_queue')


def al_recibir(canal, metodo, propiedades, cuerpo):
    try:
        guardar(json.loads(cuerpo))
    except (ValueError, KeyError, TypeError, DataError, IntegrityError):
        # Rejecting instead of requeueing: a malformed message would come back forever and
        # block the ones behind it.
        logger.exception('Evento inválido descartado: %s', propiedades.message_id)
        canal.basic_reject(metodo.delivery_tag, requeue=False)
        return
    # Ack after saving instead of on arrival: if the database is down the message stays in
    # RabbitMQ and comes back when this process reconnects.
    canal.basic_ack(metodo.delivery_tag)


class Command(BaseCommand):
    help = 'Guarda en logs.evento_log los eventos que party y queue publican en RabbitMQ.'

    def handle(self, *args, **opciones):
        if not settings.RABBITMQ_URL:
            raise CommandError('Falta LOGS_RABBITMQ_URL en .env (ver .env.example).')
        while True:
            conexion = None
            try:
                conexion = pika.BlockingConnection(pika.URLParameters(settings.RABBITMQ_URL))
                canal = conexion.channel()
                canal.basic_qos(prefetch_count=50)
                for cola in COLAS:
                    canal.basic_consume(cola, al_recibir)
                self.stdout.write(f'Consumiendo {", ".join(COLAS)}')
                canal.start_consuming()
            except FALLAS_RECUPERABLES:
                esperar_y_reintentar(conexion)
