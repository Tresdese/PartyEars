"""Convierte los eventos de party y queue en filas de logs.evento_log (RF-34, RNF-12)."""
import uuid
from datetime import datetime

from apps.mensajeria.publicador import TIPO_OPERACION
from .models import EventoLog

RECURSO_POR_SERVICIO = {'party': 'party', 'queue': 'cola'}
# Allow list instead of removing known secrets: a field added later to an event (a token, an
# invitation code, chat text) stays out of logs until someone decides it is safe.
CAMPOS_PERMITIDOS = {
    'usuario_id', 'motivo', 'puede_aportar', 'puede_modificar_cola', 'anterior_id', 'nuevo_id',
    'anfitrion_id', 'finalizada_en', 'operacion', 'resultado', 'error', 'elemento_id',
    'recurso_audio_id', 'estado', 'posicion_base_ms', 'referencia_en',
}


def _uuid(valor):
    return None if valor is None else uuid.UUID(str(valor))


def convertir(sobre):
    """Fila de evento_log a partir del sobre publicado. ValueError, KeyError o TypeError si el
    mensaje no tiene el formato esperado."""
    servicio = sobre['servicio']
    datos = sobre['datos']
    if servicio not in RECURSO_POR_SERVICIO or not isinstance(datos, dict):
        raise ValueError(f'evento de un servicio desconocido: {servicio}')

    tipo = sobre['tipo']
    resultado = datos.get('resultado') if tipo == TIPO_OPERACION else None
    if resultado is None:
        nivel, mensaje = 'info', f'{tipo} (versión {sobre["version"]})'
    else:
        nivel = 'error' if resultado >= 500 else 'warning' if resultado >= 400 else 'info'
        mensaje = f'{datos["operacion"]}: {resultado}' + (f' {datos["error"]}'
                                                         if datos.get('error') else '')
    detalle = {campo: valor for campo, valor in datos.items()
               if campo in CAMPOS_PERMITIDOS and isinstance(valor, (str, int, bool))}
    detalle['version'] = sobre['version']

    agregado_id = _uuid(sobre['agregado_id'])
    return EventoLog(
        id=_uuid(sobre['id']), servicio_codigo=servicio, tipo=tipo, nivel=nivel,
        ocurrido_en=datetime.fromisoformat(sobre['creado_en']),
        actor_usuario_id=_uuid(datos.get('actor_id')),
        # queue's aggregate is the cola, so only its operation receipts name the party.
        party_id=agregado_id if servicio == 'party' else _uuid(datos.get('party_id')),
        recurso_tipo=RECURSO_POR_SERVICIO[servicio], recurso_id=agregado_id,
        correlacion_id=_uuid(datos.get('clave')), mensaje=mensaje, detalle=detalle,
    )


def guardar(sobre):
    # ignore_conflicts (ON CONFLICT DO NOTHING) instead of failing: RabbitMQ delivers at least
    # once, and the producer keeps the event id when it resends.
    EventoLog.objects.bulk_create([convertir(sobre)], ignore_conflicts=True)
