import logging
import time

import pika
from django.db import DatabaseError, connection

logger = logging.getLogger(__name__)

# DatabaseError too instead of RabbitMQ errors alone: a missing table or a database restart
# used to stop the process for good, and nobody restarts it by hand.
FALLAS_RECUPERABLES = (pika.exceptions.AMQPError, DatabaseError)


def esperar_y_reintentar(conexion, segundos=5):
    """Cierra todo tras una falla para volver a empezar limpio.

    Cerrar la conexión con RabbitMQ devuelve a la cola los mensajes sin confirmar, y cerrar la
    de PostgreSQL obliga a Django a abrir una nueva en el siguiente intento.
    """
    logger.exception('Falló RabbitMQ o la base de datos; reintento en %s s', segundos)
    if conexion is not None and conexion.is_open:
        try:
            conexion.close()
        except pika.exceptions.AMQPError:
            pass
    connection.close()
    time.sleep(segundos)
