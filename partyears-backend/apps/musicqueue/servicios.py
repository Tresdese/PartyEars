import hashlib
import json
import uuid
from datetime import timezone as zona_utc

from django.db import connection, transaction
from django.db.models import Max
from django.utils import timezone

from apps.parties.errores import ErrorApi
from .models import Cola, ElementoCola, EventoSalida, OperacionConfirmada

OPERACION_AGREGAR = 'cola.agregar'
OPERACION_REORDENAR = 'cola.reordenar'
OPERACION_RETIRAR = 'cola.retirar'
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


def exigir_permiso(party, usuario_id, permiso):
    """El anfitrión siempre puede; los demás, según su permiso (RF-11 a RF-13)."""
    if party['anfitrion_id'] == str(usuario_id):
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


def estado_cola(cola):
    """Estado con el formato del contrato (sección 5)."""
    elementos = list(cola.elementos.filter(estado__in=ESTADOS_VISIBLES).order_by('orden'))
    actual = next((e for e in elementos if e.estado != 'pendiente'), None)
    return {
        'id': str(cola.id),
        'modalidad': 'compartida',
        'version': cola.version,
        # TODO(T-35): 'reproduccion' carries the playback state of 5.3 once playback exists.
        'actual': None if actual is None else {'elemento': formatear_elemento(actual),
                                               'reproduccion': None},
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


def _confirmar(cola, usuario_id, clave, operacion, solicitud, codigo_http, ahora):
    cola.version += 1
    cola.save(update_fields=['version'])
    OperacionConfirmada.objects.create(
        actor_id=usuario_id, clave=clave, operacion=operacion, solicitud_sha256=solicitud,
        codigo_respuesta=codigo_http, resultado={'cola_id': str(cola.id), 'version': cola.version},
        confirmada_en=ahora,
    )
    estado = estado_cola(cola)
    # TODO(T-34): the queue WebSocket (contract 7.1) does not exist yet; members only see the
    # change on their next GET.
    EventoSalida.objects.create(agregado_id=cola.id, version=cola.version,
                                tipo='cola.actualizada', datos=estado, creado_en=ahora)
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
