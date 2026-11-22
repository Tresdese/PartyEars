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
from .eventos import publicar
from .models import (AnfitrionParty, EventoSalida, InvitacionParty, MiembroParty, OperacionConfirmada, ParticipacionParty, Party)

logger = logging.getLogger(__name__)

OPERACION_CREAR = 'party.crear'
OPERACION_UNIRSE = 'party.unirse'
OPERACION_PERMISOS = 'party.permisos'
INTENTOS_CODIGO = 10
RECONEXION_CONSERVA_PERMISOS = timedelta(seconds=60)
CIERRE_NO_ES_MIEMBRO = 4003
CIERRE_PARTY_NO_EXISTE = 4004
CIERRE_PARTY_FINALIZADA = 4010

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

    OperacionConfirmada.objects.create(
        actor_id=usuario.id, clave=clave, operacion=OPERACION_CREAR, solicitud_sha256=solicitud,
        codigo_respuesta=201, resultado={'party_id': str(party.id), 'version': party.version},
        confirmada_en=ahora,
    )
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

    if miembro is None:
        miembro = MiembroParty.objects.create(party=party, usuario_id=usuario.id,
                                              incorporado_en=ahora)
    elif not _puede_conservar_permisos(party, usuario.id, ahora):
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

    OperacionConfirmada.objects.create(
        actor_id=usuario.id, clave=clave, operacion=OPERACION_UNIRSE, solicitud_sha256=solicitud,
        codigo_respuesta=200, resultado={'party_id': str(party.id), 'version': party.version},
        confirmada_en=ahora,
    )
    datos = formatear_miembro(miembro, participacion, usuario.nombre_usuario)
    EventoSalida.objects.create(agregado_id=party.id, version=party.version, tipo='miembro.ingreso',
                                creado_en=ahora, datos=datos)
    transaction.on_commit(
        lambda: _avisar_conectados(party.id, 'miembro.ingreso', datos, party.version))

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


def _avisar_conectados(party_id, tipo, datos, version):
    # Logging instead of failing the request: the join is already committed, and members
    # who miss the live event catch up through the snapshot (contract 7.5).
    try:
        async_to_sync(publicar)(str(party_id), tipo, datos, version)
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

    ahora = timezone.now()
    miembro.puede_aportar = puede_aportar
    miembro.puede_modificar_cola = puede_modificar_cola
    miembro.save(update_fields=['puede_aportar', 'puede_modificar_cola'])
    party.version += 1
    party.save(update_fields=['version'])
    OperacionConfirmada.objects.create(
        actor_id=usuario.id, clave=clave, operacion=OPERACION_PERMISOS, solicitud_sha256=solicitud,
        codigo_respuesta=200, resultado={'party_id': str(party.id), 'version': party.version},
        confirmada_en=ahora,
    )
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


def leer_clave_idempotencia(valor):
    try:
        return uuid.UUID(valor or '')
    except ValueError:
        raise ErrorApi(400, 'DATOS_INVALIDOS', 'Falta la cabecera Idempotency-Key o no es un UUID válido.')