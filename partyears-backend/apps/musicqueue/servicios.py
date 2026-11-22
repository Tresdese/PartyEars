import hashlib
import json
import logging
import uuid
from datetime import timedelta, timezone as zona_utc

from asgiref.sync import async_to_sync
from django.db import connection, transaction
from django.db.models import Max
from django.utils import timezone
from redis.exceptions import RedisError

from apps.parties.errores import ErrorApi
from apps.mensajeria.publicador import TIPO_OPERACION, datos_operacion
from apps.parties.eventos import publicar
from .models import Cola, ElementoCola, EventoSalida, OperacionConfirmada

logger = logging.getLogger(__name__)

OPERACION_AGREGAR = 'cola.agregar'
OPERACION_REORDENAR = 'cola.reordenar'
OPERACION_RETIRAR = 'cola.retirar'
OPERACION_REPRODUCCION = 'cola.reproduccion'
OPERACION_TERMINADA = 'cola.terminada'
# Same lead as the T-31 test (1.5 s): clients receive the state, pre-seek and all start at
# referencia_en instead of whenever the message reaches each one.
ADELANTO_ARRANQUE = timedelta(milliseconds=1500)
ACCIONES_DEL_ANFITRION = ('iniciar', 'pausar', 'reanudar', 'buscar')
ESTADOS_VISIBLES = ('pendiente', 'reproduciendo', 'pausada')
PERMISO_APORTAR = 'puede_aportar'
PERMISO_MODIFICAR = 'puede_modificar_cola'


def fecha_iso(valor):
    if valor is None:
        return None
    return valor.astimezone(zona_utc.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')


def huella(datos):
    texto = json.dumps(datos, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
    return hashlib.sha256(texto.encode('utf-8')).digest()


def leer_clave_idempotencia(valor):
    try:
        return uuid.UUID(valor or '')
    except ValueError:
        raise ErrorApi(400, 'DATOS_INVALIDOS',
                       'Falta la cabecera Idempotency-Key o no es un UUID válido.')


def es_anfitrion(party, usuario_id):
    return party['anfitrion_id'] == str(usuario_id)


def exigir_anfitrion(party, usuario_id):
    if not es_anfitrion(party, usuario_id):
        raise ErrorApi(403, 'NO_ES_ANFITRION', 'Solo el anfitrión controla la reproducción.')


def exigir_permiso(party, usuario_id, permiso):
    """El anfitrión siempre puede; los demás, según su permiso (RF-11 a RF-13)."""
    if es_anfitrion(party, usuario_id):
        return
    miembro = next((m for m in party['miembros'] if m['usuario_id'] == str(usuario_id)), None)
    if miembro is None or not miembro[permiso]:
        raise ErrorApi(403, 'SIN_PERMISO', 'No tienes permiso para cambiar la cola.')


def _crear_cola_si_falta(party_id):
    # ON CONFLICT instead of get_or_create: two first requests at once would both try to insert.
    with connection.cursor() as cursor:
        cursor.execute('INSERT INTO queue.cola (party_id, version_party) VALUES (%s, 0) '
                       'ON CONFLICT (party_id) DO NOTHING', [party_id])


def _bloquear_cola(party_id):
    _crear_cola_si_falta(party_id)
    return Cola.objects.select_for_update().get(party_id=party_id)


def _bloquear_clave(actor_id, clave):
    with connection.cursor() as cursor:
        cursor.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))',
                       [f'{actor_id}:{clave}'])


def formatear_elemento(elemento):
    return {
        'id': str(elemento.id),
        'recurso_audio_id': str(elemento.recurso_audio_id),
        'agregado_por': str(elemento.agregado_por),
        'orden': elemento.orden,
        'estado': elemento.estado,
        'agregado_en': fecha_iso(elemento.agregado_en),
    }


def _elemento_actual(cola):
    return cola.elementos.filter(estado__in=('reproduciendo', 'pausada')).first()


def estado_reproduccion(cola, actual):
    """Contrato 5.3. Sin actual, la reproducción está detenida."""
    return {
        'cola_id': str(cola.id),
        'version': cola.version,
        'elemento_id': str(actual.id) if actual else None,
        'recurso_audio_id': str(actual.recurso_audio_id) if actual else None,
        'estado': actual.estado if actual else 'detenida',
        'posicion_base_ms': actual.posicion_base_ms if actual else 0,
        'referencia_en': fecha_iso(actual.referencia_en) if actual else None,
        # TODO(T-14): music does not exist yet; the client ends the song by its own player.
        'duracion_ms': None,
    }


def estado_cola(cola):
    """Estado con el formato del contrato (sección 5)."""
    elementos = list(cola.elementos.filter(estado__in=ESTADOS_VISIBLES).order_by('orden'))
    actual = next((e for e in elementos if e.estado != 'pendiente'), None)
    return {
        'id': str(cola.id),
        'modalidad': 'compartida',
        'version': cola.version,
        'actual': None if actual is None else {'elemento': formatear_elemento(actual),
                                               'reproduccion': estado_reproduccion(cola, actual)},
        'pendientes': [formatear_elemento(e) for e in elementos if e.estado == 'pendiente'],
    }


def consultar_cola(party_id):
    _crear_cola_si_falta(party_id)
    return estado_cola(Cola.objects.get(party_id=party_id))


def _operacion_previa(actor_id, clave, solicitud):
    previa = OperacionConfirmada.objects.filter(actor_id=actor_id, clave=clave).first()
    if previa is not None and bytes(previa.solicitud_sha256) != solicitud:
        raise ErrorApi(409, 'IDEMPOTENCIA_CONFLICTO',
                       'Esa clave ya se usó con una solicitud distinta.')
    return previa


def _exigir_version(cola, version_esperada):
    if cola.version != version_esperada:
        raise ErrorApi(409, 'VERSION_OBSOLETA', 'La cola cambió. Recarga para ver la actual.',
                       {'version_actual': cola.version})


def _registrar_operacion(cola, usuario_id, clave, operacion, solicitud, codigo_http, ahora):
    cola.version += 1
    cola.save(update_fields=['version'])
    OperacionConfirmada.objects.create(
        actor_id=usuario_id, clave=clave, operacion=operacion, solicitud_sha256=solicitud,
        codigo_respuesta=codigo_http, resultado={'cola_id': str(cola.id), 'version': cola.version},
        confirmada_en=ahora,
    )
    # Outbox only instead of _emitir: this copy is for logs (RF-34), not for the clients.
    EventoSalida.objects.create(
        agregado_id=cola.id, version=cola.version, tipo=TIPO_OPERACION, creado_en=ahora,
        datos=datos_operacion(usuario_id, cola.party_id, operacion, codigo_http, clave=clave))


def registrar_rechazo(actor_id, party_id, operacion, error, clave):
    """RF-34: deja en el outbox una operación rechazada, después de deshacer sus cambios."""
    cola = Cola.objects.filter(party_id=party_id).first()
    if cola is None:
        return
    EventoSalida.objects.create(
        agregado_id=cola.id, version=cola.version, tipo=TIPO_OPERACION,
        datos=datos_operacion(actor_id, party_id, operacion, error.estado, error.codigo, clave))


def _avisar_en_vivo(evento, party_id):
    # Logging instead of failing the request: the change is already committed, and members
    # who miss the live event catch up through the snapshot (contract 7.5).
    try:
        async_to_sync(publicar)(str(party_id), evento.tipo, evento.datos, evento.version,
                                evento_id=evento.id)
    except (RedisError, OSError):
        logger.exception('No se pudo avisar %s de la cola %s', evento.tipo, evento.agregado_id)


def _emitir(cola, tipo, datos, ahora):
    evento = EventoSalida.objects.create(agregado_id=cola.id, version=cola.version, tipo=tipo,
                                         datos=datos, creado_en=ahora)
    # After commit instead of right away: a rolled back change must never reach the clients.
    transaction.on_commit(lambda: _avisar_en_vivo(evento, cola.party_id))


def _confirmar(cola, usuario_id, clave, operacion, solicitud, codigo_http, ahora):
    _registrar_operacion(cola, usuario_id, clave, operacion, solicitud, codigo_http, ahora)
    estado = estado_cola(cola)
    _emitir(cola, 'cola.actualizada', estado, ahora)
    return estado, codigo_http


def _elemento_pendiente(cola, elemento_id):
    elemento = cola.elementos.filter(id=elemento_id).first()
    if elemento is None:
        raise ErrorApi(404, 'NO_ENCONTRADO', 'Esa canción ya no está en la cola.')
    if elemento.estado != 'pendiente':
        raise ErrorApi(409, 'ELEMENTO_NO_PENDIENTE',
                       'Solo se pueden mover o quitar canciones que no han sonado.')
    return elemento


@transaction.atomic
def agregar_elemento(party, usuario_id, recurso_audio_id, clave):
    """RF-11. Se agrega al final y no inicia la reproducción. Devuelve (estado, código HTTP)."""
    exigir_permiso(party, usuario_id, PERMISO_APORTAR)
    _bloquear_clave(usuario_id, clave)
    solicitud = huella({'operacion': OPERACION_AGREGAR, 'party_id': party['id'],
                        'recurso_audio_id': recurso_audio_id})
    cola = _bloquear_cola(party['id'])
    previa = _operacion_previa(usuario_id, clave, solicitud)
    if previa is not None:
        return estado_cola(cola), previa.codigo_respuesta

    # TODO(T-14): check with music that the audio exists (410 AUDIO_NO_DISPONIBLE).
    ahora = timezone.now()
    ultimo = cola.elementos.aggregate(Max('orden'))['orden__max'] or 0
    ElementoCola.objects.create(cola=cola, recurso_audio_id=recurso_audio_id,
                                agregado_por=usuario_id, orden=ultimo + 1, agregado_en=ahora)
    return _confirmar(cola, usuario_id, clave, OPERACION_AGREGAR, solicitud, 201, ahora)


@transaction.atomic
def reordenar_elemento(party, usuario_id, elemento_id, nueva_posicion, version_esperada, clave):
    """RF-12. nueva_posicion cuenta desde 1 dentro de los pendientes."""
    exigir_permiso(party, usuario_id, PERMISO_MODIFICAR)
    _bloquear_clave(usuario_id, clave)
    solicitud = huella({'operacion': OPERACION_REORDENAR, 'party_id': party['id'],
                        'elemento_id': str(elemento_id), 'nueva_posicion': nueva_posicion,
                        'version_esperada': version_esperada})
    cola = _bloquear_cola(party['id'])
    previa = _operacion_previa(usuario_id, clave, solicitud)
    if previa is not None:
        return estado_cola(cola), previa.codigo_respuesta

    _exigir_version(cola, version_esperada)
    elemento = _elemento_pendiente(cola, elemento_id)
    pendientes = list(cola.elementos.filter(estado='pendiente').order_by('orden'))
    if nueva_posicion > len(pendientes):
        raise ErrorApi(400, 'DATOS_INVALIDOS', 'Esa posición no existe en la cola.',
                       {'nueva_posicion': [f'Debe estar entre 1 y {len(pendientes)}.']})

    # Reusing the pending items' own order values instead of renumbering the queue: played
    # items keep theirs. One bulk UPDATE is enough because the unique order constraint is
    # DEFERRABLE, so PostgreSQL checks it at the end of the statement, not per row.
    ordenes = [e.orden for e in pendientes]
    pendientes.remove(next(e for e in pendientes if e.id == elemento.id))
    pendientes.insert(nueva_posicion - 1, elemento)
    for nuevo_orden, pendiente in zip(ordenes, pendientes):
        pendiente.orden = nuevo_orden
    ElementoCola.objects.bulk_update(pendientes, ['orden'])
    return _confirmar(cola, usuario_id, clave, OPERACION_REORDENAR, solicitud, 200,
                      timezone.now())


@transaction.atomic
def retirar_elemento(party, usuario_id, elemento_id, version_esperada, clave):
    """RF-13. Pasa el elemento a 'retirada'; el historial no se borra."""
    exigir_permiso(party, usuario_id, PERMISO_MODIFICAR)
    _bloquear_clave(usuario_id, clave)
    solicitud = huella({'operacion': OPERACION_RETIRAR, 'party_id': party['id'],
                        'elemento_id': str(elemento_id), 'version_esperada': version_esperada})
    cola = _bloquear_cola(party['id'])
    previa = _operacion_previa(usuario_id, clave, solicitud)
    if previa is not None:
        return estado_cola(cola), previa.codigo_respuesta

    _exigir_version(cola, version_esperada)
    elemento = _elemento_pendiente(cola, elemento_id)
    ahora = timezone.now()
    elemento.estado = 'retirada'
    elemento.fin_en = ahora
    elemento.save(update_fields=['estado', 'fin_en'])
    return _confirmar(cola, usuario_id, clave, OPERACION_RETIRAR, solicitud, 200, ahora)


def _posicion_actual(elemento, ahora):
    if elemento.estado != 'reproduciendo':
        return elemento.posicion_base_ms
    # max() instead of the raw difference: during the start lead referencia_en is in the
    # future, and the song has not moved yet.
    transcurrido = max(ahora - elemento.referencia_en, timedelta(0))
    return elemento.posicion_base_ms + int(transcurrido.total_seconds() * 1000)


def _cerrar_actual(actual, estado_final, ahora):
    actual.estado = estado_final
    # max() because fin_en cannot precede referencia_en, which is in the future while the
    # song is still in its start lead.
    actual.fin_en = max(ahora, actual.referencia_en)
    actual.save(update_fields=['estado', 'fin_en'])


def _iniciar_siguiente(cola, ahora):
    """Empieza la primera pendiente desde 0; si no hay, la reproducción queda detenida."""
    siguiente = cola.elementos.filter(estado='pendiente').order_by('orden').first()
    if siguiente is None:
        return None
    siguiente.estado = 'reproduciendo'
    siguiente.inicio_en = ahora
    siguiente.referencia_en = ahora + ADELANTO_ARRANQUE
    siguiente.posicion_base_ms = 0
    siguiente.save(update_fields=['estado', 'inicio_en', 'referencia_en', 'posicion_base_ms'])
    return siguiente


def _exigir_actual(actual, elemento_id):
    # The song the user sees instead of "whatever is playing now": two skips sent at once
    # must skip one song, not two (RF-23).
    if actual is None or str(actual.id) != str(elemento_id):
        raise ErrorApi(409, 'ELEMENTO_NO_ACTUAL', 'Esa canción ya no es la que está sonando.')


def _aplicar_accion(cola, actual, accion, posicion_ms, ahora):
    """Cambia la reproducción. Devuelve el nuevo actual (None si queda detenida)."""
    if accion == 'iniciar':
        if actual is not None:
            raise ErrorApi(409, 'REPRODUCCION_EN_CURSO', 'Ya hay una canción sonando.')
        siguiente = _iniciar_siguiente(cola, ahora)
        if siguiente is None:
            raise ErrorApi(409, 'COLA_VACIA', 'Agrega una canción a la cola para empezar.')
        return siguiente

    if accion == 'saltar':
        _cerrar_actual(actual, 'omitida', ahora)
        return _iniciar_siguiente(cola, ahora)

    if accion == 'pausar' and actual.estado == 'reproduciendo':
        actual.posicion_base_ms = _posicion_actual(actual, ahora)
        actual.estado = 'pausada'
        actual.referencia_en = max(ahora, actual.referencia_en)
    elif accion == 'reanudar' and actual.estado == 'pausada':
        actual.estado = 'reproduciendo'
        actual.referencia_en = ahora + ADELANTO_ARRANQUE
    elif accion == 'buscar':
        actual.posicion_base_ms = posicion_ms
        es_pausa = actual.estado == 'pausada'
        actual.referencia_en = max(ahora, actual.referencia_en) if es_pausa else (
            ahora + ADELANTO_ARRANQUE)
    actual.save(update_fields=['estado', 'posicion_base_ms', 'referencia_en'])
    return actual


@transaction.atomic
def cambiar_reproduccion(party, usuario_id, accion, elemento_id, posicion_ms, clave):
    """Contrato 5.3. Devuelve (estado de reproducción, código HTTP)."""
    if accion in ACCIONES_DEL_ANFITRION:
        exigir_anfitrion(party, usuario_id)
    else:
        exigir_permiso(party, usuario_id, PERMISO_MODIFICAR)
    _bloquear_clave(usuario_id, clave)
    solicitud = huella({'operacion': OPERACION_REPRODUCCION, 'party_id': party['id'],
                        'accion': accion, 'elemento_id': elemento_id, 'posicion_ms': posicion_ms})
    cola = _bloquear_cola(party['id'])
    previa = _operacion_previa(usuario_id, clave, solicitud)
    actual = _elemento_actual(cola)
    if previa is not None:
        return estado_reproduccion(cola, actual), previa.codigo_respuesta

    if accion != 'iniciar':
        _exigir_actual(actual, elemento_id)
    ahora = timezone.now()
    actual = _aplicar_accion(cola, actual, accion, posicion_ms, ahora)
    _registrar_operacion(cola, usuario_id, clave, OPERACION_REPRODUCCION, solicitud, 200, ahora)
    estado = estado_reproduccion(cola, actual)
    _emitir(cola, 'reproduccion.estado', estado, ahora)
    if accion in ('iniciar', 'saltar'):
        _emitir(cola, 'cola.actualizada', estado_cola(cola), ahora)
    return estado, 200


@transaction.atomic
def terminar_elemento(party, usuario_id, elemento_id, clave):
    """RF-16. Avanza una sola vez: si ya no es el actual, responde el estado sin cambiarlo."""
    # TODO(T-14): only the host instead of any member (contract 5.3 proposal): without the
    # duration from music the server cannot tell a real end from a member skipping songs.
    exigir_anfitrion(party, usuario_id)
    _bloquear_clave(usuario_id, clave)
    solicitud = huella({'operacion': OPERACION_TERMINADA, 'party_id': party['id'],
                        'elemento_id': str(elemento_id)})
    cola = _bloquear_cola(party['id'])
    previa = _operacion_previa(usuario_id, clave, solicitud)
    actual = _elemento_actual(cola)
    if previa is not None or actual is None or actual.id != elemento_id:
        return estado_reproduccion(cola, actual), 200

    ahora = timezone.now()
    _cerrar_actual(actual, 'reproducida', ahora)
    actual = _iniciar_siguiente(cola, ahora)
    _registrar_operacion(cola, usuario_id, clave, OPERACION_TERMINADA, solicitud, 200, ahora)
    estado = estado_reproduccion(cola, actual)
    _emitir(cola, 'reproduccion.estado', estado, ahora)
    _emitir(cola, 'cola.actualizada', estado_cola(cola), ahora)
    return estado, 200
