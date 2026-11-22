"""Outbox hacia RabbitMQ (diseño de BD 2.4): party y queue publican sus eventos aquí."""
import json
import logging

import pika
from django.db import transaction
from django.db.models import F
from django.utils import timezone

logger = logging.getLogger(__name__)

TIPO_OPERACION = 'operacion.registrada'


def datos_operacion(actor_id, party_id, operacion, resultado, error=None, clave=None):
    """Recibo de una operación para logs (RF-34): quién, en qué party, qué y cómo terminó."""
    return {'actor_id': str(actor_id), 'party_id': str(party_id), 'operacion': operacion,
            'resultado': resultado, 'error': error, 'clave': None if clave is None else str(clave)}


def sobre(evento, servicio):
    return {'id': str(evento.id), 'servicio': servicio, 'tipo': evento.tipo,
            'agregado_id': str(evento.agregado_id), 'version': evento.version,
            'creado_en': evento.creado_en.isoformat(), 'datos': evento.datos}


def publicar_pendientes(canal, modelo, exchange, servicio, limite=100):
    """Publica en orden los eventos sin publicar. Devuelve cuántos confirmó RabbitMQ.

    El canal debe tener confirm_delivery: basic_publish espera la confirmación y falla si el
    broker rechaza el mensaje o no tiene cola a dónde mandarlo.
    """
    publicados = 0
    with transaction.atomic():
        pendientes = (modelo.objects.select_for_update(skip_locked=True)
                      .filter(publicado_en__isnull=True).order_by('creado_en', 'id')[:limite])
        for evento in pendientes:
            try:
                canal.basic_publish(
                    exchange, evento.tipo, json.dumps(sobre(evento, servicio)).encode(),
                    pika.BasicProperties(content_type='application/json', delivery_mode=2,
                                         message_id=str(evento.id)),
                    mandatory=True)
            except (pika.exceptions.UnroutableError, pika.exceptions.NackError):
                # Stopping instead of skipping it: the next events of the same party must not
                # overtake it, or consumers would apply them out of order.
                modelo.objects.filter(id=evento.id).update(intentos=F('intentos') + 1)
                logger.warning('RabbitMQ no aceptó el evento %s (%s)', evento.id, evento.tipo)
                break
            # max() instead of now alone: creado_en may come from another machine's clock and
            # the table requires publicado_en >= creado_en.
            modelo.objects.filter(id=evento.id).update(
                publicado_en=max(timezone.now(), evento.creado_en))
            publicados += 1
    return publicados
