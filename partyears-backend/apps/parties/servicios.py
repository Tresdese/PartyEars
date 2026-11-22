import hashlib
import json
import logging
import uuid
from datetime import timedelta, timezone as zona_utc
from asgiref.sync import async_to_sync
from django.conf import settings
from django.db import IntegrityError, connection, transaction
from django.utils import timezone
from redis.exceptions import RedisError
from .codigos import generar_codigo
from .errores import ErrorApi
from apps.mensajeria.publicador import TIPO_OPERACION, datos_operacion

from .eventos import publicar
from .models import (AnfitrionParty, EventoSalida, InvitacionParty, MiembroParty, OperacionConfirmada, ParticipacionParty, Party)

logger = logging.getLogger(__name__)

OPERACION_CREAR = 'party.crear'
OPERACION_UNIRSE = 'party.unirse'
OPERACION_PERMISOS = 'party.permisos'
OPERACION_SALIR = 'party.salir'
OPERACION_FINALIZAR = 'party.finalizar'
OPERACION_EXPULSAR = 'party.expulsar'
OPERACION_REHABILITAR = 'party.rehabilitar'
OPERACION_TRANSFERIR = 'party.transferir'
INTENTOS_CODIGO = 10
RECONEXION_CONSERVA_PERMISOS = timedelta(seconds=60)
CIERRE_NO_ES_MIEMBRO = 4003
CIERRE_PARTY_NO_EXISTE = 4004
CIERRE_PARTY_FINALIZADA = 4010
CIERRE_SIN_LATIDO = 4009

def fecha_iso(valor):
    if valor is None:
        return None
    return valor.astimezone(zona_utc.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')

def huella(datos):
    texto = json.dumps(datos, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
    return hashlib.sha256(texto.encode('utf-8')).digest()

def _bloquear_clave(actor_id, clave):
    with connection.cursor() as cursor:
        cursor.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))', [f'{actor_id}:{clave}'])

def _error_ya_en_otra_party():
    return ErrorApi(409, 'YA_EN_OTRA_PARTY', 'Ya estás en otra party. Sal de ella para continuar.')

def _emitir_invitacion(party, usuario_id, ahora):
    for _ in range(INTENTOS_CODIGO):
        try:
            with transaction.atomic():
                return InvitacionParty.objects.create(
                    party=party,
                    codigo=generar_codigo(),
                    creada_por=usuario_id,
                    creada_en=ahora,
                    expira_en=ahora + settings.PARTY_VIGENCIA_CODIGO,
                )
        except IntegrityError:
            continue

    raise ErrorApi(503, 'SERVICIO_NO_DISPONIBLE', 'No fue posible crear la party. Intenta nuevamente.')

@transaction.atomic
def crear_party(usuario, nombre, recurso_audio_id_inicial, clave):
    """Crea la party completa en una transacción. Devuelve (estado, código HTTP)."""
    _bloquear_clave(usuario.id, clave)

    solicitud = huella({
        'operacion': OPERACION_CREAR,
        'nombre': nombre,
        'recurso_audio_id_inicial': recurso_audio_id_inicial,
    })

    previa = OperacionConfirmada.objects.filter(actor_id=usuario.id, clave=clave).first()
    if previa is not None:
        if bytes(previa.solicitud_sha256) != solicitud:
            raise ErrorApi(409, 'IDEMPOTENCIA_CONFLICTO', 'Esa clave ya se usó con una solicitud distinta.')
        party = Party.objects.get(id=previa.resultado['party_id'])
        return estado_completo(party, usuario), previa.codigo_respuesta

    if ParticipacionParty.objects.filter(usuario_id=usuario.id, salida_en__isnull=True).exists():
        raise _error_ya_en_otra_party()

    ahora = timezone.now()
    party = Party.objects.create(nombre=nombre, creada_por=usuario.id, version=1, creada_en=ahora)
    MiembroParty.objects.create(party=party, usuario_id=usuario.id, puede_aportar=True, puede_modificar_cola=True, incorporado_en=ahora)
    AnfitrionParty.objects.create(party=party, usuario_id=usuario.id, asignado_en=ahora)

    try:
        with transaction.atomic():
            ParticipacionParty.objects.create(party=party, usuario_id=usuario.id, entrada_en=ahora)
    except IntegrityError:
        raise _error_ya_en_otra_party()

    _emitir_invitacion(party, usuario.id, ahora)

    _confirmar_operacion(party, usuario.id, clave, OPERACION_CREAR, solicitud, 201, ahora)
    EventoSalida.objects.create(
        agregado_id=party.id, version=party.version, tipo='party.creada', creado_en=ahora,
        datos={'party_id': str(party.id), 'nombre': party.nombre, 'anfitrion_id': str(usuario.id)},
    )

    return estado_completo(party, usuario), 201

def party_actual(usuario):
    participacion = (ParticipacionParty.objects.select_related('party').filter(usuario_id=usuario.id, salida_en__isnull=True, party__finalizada_en__isnull=True).first())
    if participacion is None:
        return None

    return estado_completo(participacion.party, usuario, renovar_codigo=True)


def formatear_miembro(miembro, participacion, nombre_usuario):
    """Miembro con el formato del contrato (sección 4)."""
    return {
        'usuario_id': str(miembro.usuario_id),
        'nombre_usuario': nombre_usuario,
        'puede_aportar': miembro.puede_aportar,
        'puede_modificar_cola': miembro.puede_modificar_cola,
        'estado': miembro.estado,
        'conectado': participacion is not None,
        'orden_ingreso': participacion.orden_ingreso if participacion else None,
    }


@transaction.atomic
def unirse_party(usuario, codigo, clave):
    """Ingreso por código como oyente (RF-08, RF-36). Devuelve (estado, código HTTP)."""
    _bloquear_clave(usuario.id, clave)

    solicitud = huella({'operacion': OPERACION_UNIRSE, 'codigo': codigo})
    previa = OperacionConfirmada.objects.filter(actor_id=usuario.id, clave=clave).first()
    if previa is not None:
        if bytes(previa.solicitud_sha256) != solicitud:
            raise ErrorApi(409, 'IDEMPOTENCIA_CONFLICTO',
                           'Esa clave ya se usó con una solicitud distinta.')
        party = Party.objects.get(id=previa.resultado['party_id'])
        return estado_completo(party, usuario), previa.codigo_respuesta

    invitacion = InvitacionParty.objects.filter(codigo=codigo, revocada_en__isnull=True).first()
    if invitacion is None:
        raise ErrorApi(404, 'CODIGO_INVALIDO', 'Ese código no corresponde a ninguna party.')

    # Row lock instead of counting alone: two simultaneous joins would both see 19
    # connected and both enter.
    party = Party.objects.select_for_update().get(id=invitacion.party_id)
    ahora = timezone.now()
    if party.finalizada_en is not None:
        raise ErrorApi(410, 'PARTY_FINALIZADA', 'Esa party ya terminó.')
    if invitacion.expira_en <= ahora:
        raise ErrorApi(410, 'CODIGO_EXPIRADO',
                       'El código ya venció. Pídele uno nuevo al anfitrión.')

    miembro = MiembroParty.objects.filter(party=party, usuario_id=usuario.id).first()
    if miembro is not None and miembro.estado == 'expulsado':
        raise ErrorApi(403, 'USUARIO_EXPULSADO', 'El anfitrión te sacó de esta party.')

    abierta = (ParticipacionParty.objects
               .filter(usuario_id=usuario.id, salida_en__isnull=True).first())
    if abierta is not None:
        if abierta.party_id != party.id:
            raise _error_ya_en_otra_party()
        return estado_completo(party, usuario), 200

    if party.participaciones.filter(salida_en__isnull=True).count() >= party.capacidad:
        raise ErrorApi(409, 'PARTY_LLENA', 'La party ya tiene el máximo de personas conectadas.')

    reconecta = False
    if miembro is None:
        miembro = MiembroParty.objects.create(party=party, usuario_id=usuario.id,
                                              incorporado_en=ahora)
    elif _puede_conservar_permisos(party, usuario.id, ahora):
        reconecta = True
    else:
        MiembroParty.objects.filter(id=miembro.id).update(puede_aportar=False,
                                                          puede_modificar_cola=False)
        miembro.puede_aportar = miembro.puede_modificar_cola = False

    try:
        with transaction.atomic():
            participacion = ParticipacionParty.objects.create(party=party, usuario_id=usuario.id,
                                                              entrada_en=ahora)
    except IntegrityError:
        # Unique index instead of trusting the check above: the same user may be joining
        # or creating another party in parallel.
        raise _error_ya_en_otra_party()
    participacion.refresh_from_db(fields=['orden_ingreso'])

    party.version += 1
    Party.objects.filter(id=party.id).update(version=party.version)

    _confirmar_operacion(party, usuario.id, clave, OPERACION_UNIRSE, solicitud, 200, ahora)
    if reconecta:
        tipo, datos = 'miembro.reconectado', {'usuario_id': str(usuario.id)}
    else:
        tipo = 'miembro.ingreso'
        datos = formatear_miembro(miembro, participacion, usuario.nombre_usuario)
    EventoSalida.objects.create(agregado_id=party.id, version=party.version, tipo=tipo,
                                creado_en=ahora, datos=datos)
    transaction.on_commit(lambda: _avisar_conectados(party.id, tipo, datos, party.version))

    return estado_completo(party, usuario), 200


def _puede_conservar_permisos(party, usuario_id, ahora):
    """RF-21: within 60 s of a disconnection the member keeps their permissions."""
    ultima = (party.participaciones.filter(usuario_id=usuario_id, salida_en__isnull=False)
              .order_by('-salida_en').first())
    return (ultima is not None and ultima.motivo_salida == 'desconexion'
            and ahora - ultima.salida_en <= RECONEXION_CONSERVA_PERMISOS)


def _esta_dentro(party, usuario_id):
    # Open participation instead of membership alone: whoever left or was expelled keeps
    # their member row, but must not keep reading or changing the party.
    esta_conectado = party.participaciones.filter(usuario_id=usuario_id,
                                                  salida_en__isnull=True).exists()
    esta_habilitado = party.miembros.filter(usuario_id=usuario_id, estado='habilitado').exists()
    return esta_conectado and esta_habilitado


def verificar_acceso_websocket(party_id, usuario_id):
    """Contrato 7.2. Devuelve (código de cierre o None, versión de la party)."""
    party = Party.objects.filter(id=party_id).first()
    if party is None:
        return CIERRE_PARTY_NO_EXISTE, None
    if party.finalizada_en is not None:
        return CIERRE_PARTY_FINALIZADA, None
    if not _esta_dentro(party, usuario_id):
        return CIERRE_NO_ES_MIEMBRO, None
    return None, party.version


def consultar_party(usuario, party_id):
    """Contrato 4.3: instantánea para el cliente y para validar permisos desde queue."""
    party = Party.objects.filter(id=party_id).first()
    if party is None:
        raise ErrorApi(404, 'NO_ENCONTRADO', 'Esa party no existe.')
    if party.finalizada_en is not None:
        raise ErrorApi(410, 'PARTY_FINALIZADA', 'La party ya terminó.')
    if not _esta_dentro(party, usuario.id):
        raise ErrorApi(403, 'NO_ES_MIEMBRO', 'No estás dentro de esta party.')
    return estado_completo(party, usuario)


def _avisar_conectados(party_id, tipo, datos, version, evento_id=None):
    # Logging instead of failing the request: the join is already committed, and members
    # who miss the live event catch up through the snapshot (contract 7.5).
    try:
        async_to_sync(publicar)(str(party_id), tipo, datos, version, evento_id=evento_id)
    except (RedisError, OSError):
        logger.exception('No se pudo avisar %s de la party %s', tipo, party_id)


def estado_completo(party, usuario, renovar_codigo=False):
    """Estado de la party con el formato del contrato (sección 4)."""
    anfitrion = AnfitrionParty.objects.get(party=party)
    es_anfitrion = anfitrion.usuario_id == usuario.id

    abiertas = {p.usuario_id: p for p in party.participaciones.filter(salida_en__isnull=True)}

    codigo = None
    if es_anfitrion:
        invitacion = party.invitaciones.filter(revocada_en__isnull=True).order_by('-creada_en').first()
        if invitacion is not None:
            if renovar_codigo and party.finalizada_en is None:
                invitacion.expira_en = timezone.now() + settings.PARTY_VIGENCIA_CODIGO
                invitacion.save(update_fields=['expira_en'])
            codigo = invitacion.codigo

    miembros = [
        formatear_miembro(miembro, abiertas.get(miembro.usuario_id),
                        usuario.nombre_usuario if miembro.usuario_id == usuario.id else None)
        for miembro in party.miembros.order_by('id')
    ]

    return {
        'id': str(party.id),
        'nombre': party.nombre,
        'codigo': codigo,
        'version': party.version,
        'creada_en': fecha_iso(party.creada_en),
        'finalizada_en': fecha_iso(party.finalizada_en),
        'anfitrion_id': str(anfitrion.usuario_id),
        'cola_id': None,
        'miembros': miembros,
    }


@transaction.atomic
def cambiar_permisos(usuario, party_id, miembro_id, puede_aportar, puede_modificar_cola,
                     version_esperada, clave):
    """RF-17, RF-18. Devuelve ({miembro, version}, código HTTP)."""
    _bloquear_clave(usuario.id, clave)
    solicitud = huella({'operacion': OPERACION_PERMISOS, 'party_id': str(party_id),
                        'usuario_id': str(miembro_id), 'puede_aportar': puede_aportar,
                        'puede_modificar_cola': puede_modificar_cola,
                        'version_esperada': version_esperada})
    party = Party.objects.select_for_update().filter(id=party_id).first()
    if party is None:
        raise ErrorApi(404, 'NO_ENCONTRADO', 'Esa party no existe.')
    miembro = party.miembros.filter(usuario_id=miembro_id).first()

    previa = OperacionConfirmada.objects.filter(actor_id=usuario.id, clave=clave).first()
    if previa is not None:
        if bytes(previa.solicitud_sha256) != solicitud:
            raise ErrorApi(409, 'IDEMPOTENCIA_CONFLICTO',
                           'Esa clave ya se usó con una solicitud distinta.')
        return _resultado_permisos(party, miembro), previa.codigo_respuesta

    if party.finalizada_en is not None:
        raise ErrorApi(410, 'PARTY_FINALIZADA', 'La party ya terminó.')
    if AnfitrionParty.objects.get(party=party).usuario_id != usuario.id:
        raise ErrorApi(403, 'NO_ES_ANFITRION', 'Solo el anfitrión puede cambiar los permisos.')
    if party.version != version_esperada:
        raise ErrorApi(409, 'VERSION_OBSOLETA', 'La party cambió. Recarga para ver la actual.',
                       {'version_actual': party.version})
    if miembro is None:
        raise ErrorApi(404, 'NO_ENCONTRADO', 'Esa persona no está en la party.')
    if miembro.usuario_id == usuario.id:
        raise ErrorApi(400, 'DATOS_INVALIDOS', 'El anfitrión siempre tiene todos los permisos.')
    # Granting needs the member connected (CU-13 FA-4.1); revoking does not (CU-14 FA-5.1), so
    # a host can still take permissions away from someone who dropped.
    otorga = ((puede_aportar and not miembro.puede_aportar)
              or (puede_modificar_cola and not miembro.puede_modificar_cola))
    esta_conectado = party.participaciones.filter(usuario_id=miembro.usuario_id,
                                                  salida_en__isnull=True).exists()
    if otorga and not esta_conectado:
        raise ErrorApi(409, 'PARTICIPANTE_NO_CONECTADO',
                       'El participante ya no está conectado a la party.')

    ahora = timezone.now()
    miembro.puede_aportar = puede_aportar
    miembro.puede_modificar_cola = puede_modificar_cola
    miembro.save(update_fields=['puede_aportar', 'puede_modificar_cola'])
    party.version += 1
    party.save(update_fields=['version'])
    _confirmar_operacion(party, usuario.id, clave, OPERACION_PERMISOS, solicitud, 200, ahora)
    datos = {'usuario_id': str(miembro.usuario_id), 'puede_aportar': puede_aportar,
             'puede_modificar_cola': puede_modificar_cola}
    EventoSalida.objects.create(agregado_id=party.id, version=party.version,
                                tipo='miembro.permisos', datos=datos, creado_en=ahora)
    transaction.on_commit(
        lambda: _avisar_conectados(party.id, 'miembro.permisos', datos, party.version))
    return _resultado_permisos(party, miembro), 200


def _resultado_permisos(party, miembro):
    participacion = party.participaciones.filter(usuario_id=miembro.usuario_id,
                                                 salida_en__isnull=True).first()
    return {'miembro': formatear_miembro(miembro, participacion, None), 'version': party.version}


def _confirmar_operacion(party, actor_id, clave, operacion, solicitud, codigo_respuesta, ahora):
    """Recibo de idempotencia (contrato 1.6) y su copia para logs en el outbox (RF-34)."""
    OperacionConfirmada.objects.create(
        actor_id=actor_id, clave=clave, operacion=operacion, solicitud_sha256=solicitud,
        codigo_respuesta=codigo_respuesta,
        resultado={'party_id': str(party.id), 'version': party.version}, confirmada_en=ahora,
    )
    EventoSalida.objects.create(
        agregado_id=party.id, version=party.version, tipo=TIPO_OPERACION, creado_en=ahora,
        datos=datos_operacion(actor_id, party.id, operacion, codigo_respuesta, clave=clave))


def registrar_rechazo(actor_id, party_id, operacion, error, clave):
    """RF-34: deja en el outbox una operación rechazada, después de deshacer sus cambios."""
    party = Party.objects.filter(id=party_id).first()
    if party is None:
        return
    EventoSalida.objects.create(
        agregado_id=party.id, version=party.version, tipo=TIPO_OPERACION,
        datos=datos_operacion(actor_id, party.id, operacion, error.estado, error.codigo, clave))


def _buscar_operacion_previa(usuario, clave, solicitud):
    """Idempotencia (contrato 1.6): la misma clave con la misma solicitud repite el resultado."""
    previa = OperacionConfirmada.objects.filter(actor_id=usuario.id, clave=clave).first()
    if previa is not None and bytes(previa.solicitud_sha256) != solicitud:
        raise ErrorApi(409, 'IDEMPOTENCIA_CONFLICTO', 'Esa clave ya se usó con una solicitud distinta.')
    return previa


def _registrar_evento(party, tipo, datos, ahora, pendientes):
    """Deja el evento en el outbox con la versión siguiente de la party.

    Cada evento sube la versión en uno, así el cliente detecta un evento perdido por el salto
    (contrato 7.5). `pendientes` junta lo que se avisa por WebSocket cuando se confirme todo.
    """
    party.version += 1
    evento = EventoSalida.objects.create(agregado_id=party.id, version=party.version, tipo=tipo, datos=datos, creado_en=ahora)
    pendientes.append((evento.id, tipo, datos, party.version))


def _guardar_version_y_avisar(party, pendientes):
    Party.objects.filter(id=party.id).update(version=party.version)

    def avisar():
        # One callback for all events instead of one each: they must go out in order.
        for evento_id, tipo, datos, version in pendientes:
            _avisar_conectados(party.id, tipo, datos, version, evento_id)

    transaction.on_commit(avisar)


def conectados_habilitados(party):
    """Participaciones abiertas de miembros habilitados: quienes sostienen la party (RF-20)."""
    return party.participaciones.filter(
        salida_en__isnull=True,
        usuario_id__in=party.miembros.filter(estado='habilitado').values('usuario_id'))


def aplicar_sucesion(party, anfitrion, ahora, pendientes):
    """RF-22: el cargo pasa al primero por orden de ingreso entre conectados y habilitados.

    Quien llama garantiza que el anfitrión actual ya no está conectado y que hay al menos un
    candidato. T-39 reutiliza esta función desde la detección de desconexión.
    """
    candidato = conectados_habilitados(party).order_by('orden_ingreso').first()
    miembro = party.miembros.get(usuario_id=candidato.usuario_id)
    _asignar_anfitrion(party, anfitrion.usuario_id, miembro, 'sucesion', ahora, pendientes)


def _asignar_anfitrion(party, anterior_id, miembro, motivo, ahora, pendientes):
    """Cambio de cargo común a la sucesión (RF-22) y a la transferencia manual (RF-31)."""
    AnfitrionParty.objects.filter(party=party).update(usuario_id=miembro.usuario_id,
                                                      asignado_en=ahora)
    _registrar_evento(party, 'anfitrion.cambio',
                      {'anterior_id': str(anterior_id),
                       'nuevo_id': str(miembro.usuario_id), 'motivo': motivo},
                      ahora, pendientes)

    # El anfitrión siempre tiene todos los permisos (4.4); el oyente que hereda el cargo no.
    if not (miembro.puede_aportar and miembro.puede_modificar_cola):
        MiembroParty.objects.filter(id=miembro.id).update(puede_aportar=True, puede_modificar_cola=True)
        _registrar_evento(party, 'miembro.permisos',
                          {'usuario_id': str(miembro.usuario_id), 'puede_aportar': True,
                           'puede_modificar_cola': True}, ahora, pendientes)


def finalizar_sin_conectados(party, ahora, pendientes):
    """RF-20, CU-16 FA-0.1: cierre automático. Quien llama tiene la party bloqueada."""
    if not conectados_habilitados(party).exists():
        _finalizar(party, 'sin_conectados', ahora, pendientes)


def _finalizar(party, motivo, ahora, pendientes):
    # El código de invitación no se revoca: unirse comprueba finalizada_en antes y responde
    # 410 PARTY_FINALIZADA (contrato 4.2), más claro que un 404 de código inválido.
    party.participaciones.filter(salida_en__isnull=True).update(salida_en=ahora, motivo_salida='fin_party')
    party.finalizada_en = ahora
    Party.objects.filter(id=party.id).update(finalizada_en=ahora)
    _registrar_evento(party, 'party.finalizada', {'finalizada_en': fecha_iso(ahora), 'motivo': motivo}, ahora, pendientes)


def _party_bloqueada(party_id):
    party = Party.objects.select_for_update().filter(id=party_id).first()
    if party is None:
        raise ErrorApi(404, 'NO_ENCONTRADO', 'Esa party no existe.')
    return party


@transaction.atomic
def salir_party(usuario, party_id, clave):
    """RF-19, RF-20, RF-22. Devuelve (None, 204)."""
    _bloquear_clave(usuario.id, clave)
    solicitud = huella({'operacion': OPERACION_SALIR, 'party_id': str(party_id)})
    # Row lock: two members leaving at once must not both see the other as still connected,
    # or nobody would close the party.
    party = _party_bloqueada(party_id)

    previa = _buscar_operacion_previa(usuario, clave, solicitud)
    if previa is not None:
        return None, previa.codigo_respuesta

    if party.finalizada_en is not None:
        raise ErrorApi(410, 'PARTY_FINALIZADA', 'La party ya terminó.')
    participacion = party.participaciones.filter(usuario_id=usuario.id,
                                                 salida_en__isnull=True).first()
    if participacion is None:
        raise ErrorApi(403, 'NO_ES_MIEMBRO', 'No estás dentro de esta party.')

    ahora = timezone.now()
    participacion.salida_en = ahora
    participacion.motivo_salida = 'voluntaria'
    participacion.save(update_fields=['salida_en', 'motivo_salida'])

    pendientes = []
    _registrar_evento(party, 'miembro.salida',
                      {'usuario_id': str(usuario.id), 'motivo': 'voluntaria'}, ahora, pendientes)
    if not conectados_habilitados(party).exists():
        _finalizar(party, 'sin_conectados', ahora, pendientes)
    else:
        anfitrion = AnfitrionParty.objects.get(party=party)
        if anfitrion.usuario_id == usuario.id:
            aplicar_sucesion(party, anfitrion, ahora, pendientes)

    _confirmar_operacion(party, usuario.id, clave, OPERACION_SALIR, solicitud, 204, ahora)
    _guardar_version_y_avisar(party, pendientes)
    return None, 204


@transaction.atomic
def desconectar_participante(party_id, usuario_id):
    """RF-21, RNF-07. El servidor dejó de saber de la persona: cierra su participación.

    Queda cerrada con motivo `desconexion`; los 60 s para conservar los permisos se cuentan
    desde esa fecha cuando vuelve por `unirse` (_puede_conservar_permisos). No usa
    Idempotency-Key porque no es una operación del cliente. Devuelve True si cerró una
    participación y False si no había nada que cerrar (ya salió, la expulsaron o la party
    terminó), así `salir` y `finalizar` pueden cerrar sockets sin duplicar avisos.
    """
    party = Party.objects.select_for_update().filter(id=party_id).first()
    if party is None or party.finalizada_en is not None:
        return False
    participacion = party.participaciones.filter(usuario_id=usuario_id,
                                                 salida_en__isnull=True).first()
    if participacion is None:
        return False

    ahora = timezone.now()
    participacion.salida_en = ahora
    participacion.motivo_salida = 'desconexion'
    participacion.save(update_fields=['salida_en', 'motivo_salida'])

    pendientes = []
    _registrar_evento(party, 'miembro.desconectado', {'usuario_id': str(usuario_id)}, ahora,
                      pendientes)
    if not conectados_habilitados(party).exists():
        _finalizar(party, 'sin_conectados', ahora, pendientes)
    else:
        anfitrion = AnfitrionParty.objects.get(party=party)
        if str(anfitrion.usuario_id) == str(usuario_id):
            aplicar_sucesion(party, anfitrion, ahora, pendientes)
    _guardar_version_y_avisar(party, pendientes)
    return True


@transaction.atomic
def finalizar_party(usuario, party_id, clave):
    """RF-18, RF-20. Devuelve (None, 204)."""
    _bloquear_clave(usuario.id, clave)
    solicitud = huella({'operacion': OPERACION_FINALIZAR, 'party_id': str(party_id)})
    party = _party_bloqueada(party_id)

    previa = _buscar_operacion_previa(usuario, clave, solicitud)
    if previa is not None:
        return None, previa.codigo_respuesta

    if party.finalizada_en is not None:
        raise ErrorApi(410, 'PARTY_FINALIZADA', 'La party ya terminó.')
    if not _esta_dentro(party, usuario.id):
        raise ErrorApi(403, 'NO_ES_MIEMBRO', 'No estás dentro de esta party.')
    if AnfitrionParty.objects.get(party=party).usuario_id != usuario.id:
        raise ErrorApi(403, 'NO_ES_ANFITRION', 'Solo el anfitrión puede finalizar la party.')

    ahora = timezone.now()
    pendientes = []
    _finalizar(party, 'anfitrion', ahora, pendientes)

    _confirmar_operacion(party, usuario.id, clave, OPERACION_FINALIZAR, solicitud, 204, ahora)
    _guardar_version_y_avisar(party, pendientes)
    return None, 204


@transaction.atomic
def _administrar_miembro(usuario, party_id, miembro_id, version_esperada, clave, operacion,
                         aplicar):
    """Validación común de las operaciones del anfitrión sobre otro miembro (contrato 4.5).

    Devuelve (None, 204). La party queda bloqueada, así que dos operaciones simultáneas del
    mismo anfitrión se aplican una tras otra y la segunda ve la versión ya cambiada.
    """
    _bloquear_clave(usuario.id, clave)
    solicitud = huella({'operacion': operacion, 'party_id': str(party_id),
                        'usuario_id': str(miembro_id), 'version_esperada': version_esperada})
    party = _party_bloqueada(party_id)

    previa = _buscar_operacion_previa(usuario, clave, solicitud)
    if previa is not None:
        return None, previa.codigo_respuesta

    if party.finalizada_en is not None:
        raise ErrorApi(410, 'PARTY_FINALIZADA', 'La party ya terminó.')
    if AnfitrionParty.objects.get(party=party).usuario_id != usuario.id:
        raise ErrorApi(403, 'NO_ES_ANFITRION', 'Solo el anfitrión puede hacer esto.')
    if party.version != version_esperada:
        raise ErrorApi(409, 'VERSION_OBSOLETA', 'La party cambió. Recarga para ver la actual.',
                       {'version_actual': party.version})
    # CU-23 FA-01: the host leaves through salir or finalizar, never by expelling themselves.
    if miembro_id == usuario.id:
        raise ErrorApi(400, 'DATOS_INVALIDOS', 'Esa acción no se puede aplicar a ti mismo.')
    miembro = party.miembros.filter(usuario_id=miembro_id).first()
    if miembro is None:
        raise ErrorApi(404, 'NO_ENCONTRADO', 'Esa persona no está en la party.')

    ahora = timezone.now()
    pendientes = []
    aplicar(party, miembro, ahora, pendientes)
    _confirmar_operacion(party, usuario.id, clave, operacion, solicitud, 204, ahora)
    _guardar_version_y_avisar(party, pendientes)
    return None, 204


def _expulsar(party, miembro, ahora, pendientes):
    # Already expelled instead of an error: the result the host wants is already in place.
    if miembro.estado == 'expulsado':
        return
    # Permissions dropped too: once rehabilitated, the member comes back as a listener (4.5).
    MiembroParty.objects.filter(id=miembro.id).update(estado='expulsado', puede_aportar=False,
                                                      puede_modificar_cola=False)
    usuario_id = str(miembro.usuario_id)
    # miembro.expulsado first: the server closes the expelled member's socket on it, so the
    # member still learns why before the socket goes away.
    _registrar_evento(party, 'miembro.expulsado', {'usuario_id': usuario_id}, ahora, pendientes)
    abiertas = party.participaciones.filter(usuario_id=miembro.usuario_id, salida_en__isnull=True)
    if abiertas.update(salida_en=ahora, motivo_salida='expulsion'):
        _registrar_evento(party, 'miembro.salida', {'usuario_id': usuario_id,
                                                    'motivo': 'expulsion'}, ahora, pendientes)
    # TODO(T-41): streaming must end the member's voice when it consumes miembro.expulsado.
    finalizar_sin_conectados(party, ahora, pendientes)


def _rehabilitar(party, miembro, ahora, pendientes):
    if miembro.estado == 'habilitado':
        return
    MiembroParty.objects.filter(id=miembro.id).update(estado='habilitado')
    _registrar_evento(party, 'miembro.rehabilitado', {'usuario_id': str(miembro.usuario_id)},
                      ahora, pendientes)


def expulsar_miembro(usuario, party_id, miembro_id, version_esperada, clave):
    """RF-30, CU-23."""
    return _administrar_miembro(usuario, party_id, miembro_id, version_esperada, clave,
                                OPERACION_EXPULSAR, _expulsar)


def rehabilitar_miembro(usuario, party_id, miembro_id, version_esperada, clave):
    """RF-30, CU-23: retira la prohibición sin conectarlo; debe volver a unirse."""
    return _administrar_miembro(usuario, party_id, miembro_id, version_esperada, clave,
                                OPERACION_REHABILITAR, _rehabilitar)


def _transferir(party, miembro, ahora, pendientes):
    # CU-24 FA-01: the recipient must still be inside; whoever dropped or was expelled cannot
    # take a role they would not be there to exercise.
    if not _esta_dentro(party, miembro.usuario_id):
        raise ErrorApi(409, 'DESTINATARIO_NO_ELEGIBLE',
                       'Esa persona ya no está conectada a la party.')
    # The previous host keeps their contribution permissions: CU-24 only removes the host-only
    # powers, and those follow AnfitrionParty, not these flags.
    anterior_id = AnfitrionParty.objects.get(party=party).usuario_id
    _asignar_anfitrion(party, anterior_id, miembro, 'manual', ahora, pendientes)


def transferir_anfitrion(usuario, party_id, destinatario_id, version_esperada, clave):
    """RF-31, CU-24."""
    return _administrar_miembro(usuario, party_id, destinatario_id, version_esperada, clave,
                                OPERACION_TRANSFERIR, _transferir)


def leer_clave_idempotencia(valor):
    try:
        return uuid.UUID(valor or '')
    except ValueError:
        raise ErrorApi(400, 'DATOS_INVALIDOS', 'Falta la cabecera Idempotency-Key o no es un UUID válido.')