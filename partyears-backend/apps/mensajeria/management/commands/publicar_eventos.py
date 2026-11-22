import logging
import time

import pika
from django.apps import apps
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.mensajeria.publicador import publicar_pendientes

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Publica en RabbitMQ los eventos del outbox de este servicio (party o queue).'

    def handle(self, *args, **opciones):
        if not settings.RABBITMQ_URL:
            raise CommandError('Falta <SERVICIO>_RABBITMQ_URL en .env (ver .env.example).')
        modelo = apps.get_model(settings.OUTBOX_MODELO)
        while True:
            try:
                conexion = pika.BlockingConnection(pika.URLParameters(settings.RABBITMQ_URL))
                canal = conexion.channel()
                canal.confirm_delivery()
                self.stdout.write(f'Publicando en {settings.RABBITMQ_EXCHANGE}')
                while True:
                    if not publicar_pendientes(canal, modelo, settings.RABBITMQ_EXCHANGE,
                                               settings.SERVICIO):
                        # conexion.sleep instead of time.sleep: it keeps answering heartbeats.
                        conexion.sleep(1)
            except pika.exceptions.AMQPError:
                logger.exception('Se perdió la conexión con RabbitMQ; reintento en 5 s')
                time.sleep(5)
