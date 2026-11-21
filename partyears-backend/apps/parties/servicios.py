import hashlib
import json
import uuid
from datetime import timezone as zona_utc
from django.conf import settings
from django.db import IntegrityError, connection, transaction
from django.utils import timezone
from .codigos import generar_codigo
from .errores import ErrorApi
from .models import (AnfitrionParty, EventoSalida, InvitacionParty, MiembroParty, OperacionConfirmada, ParticipacionParty, Party)

OPERACION_CREAR = 'party.crear'
INTENTOS_CODIGO = 10

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

    miembros = []
    for miembro in party.miembros.order_by('id'):
        participacion = abiertas.get(miembro.usuario_id)
        miembros.append({
            'usuario_id': str(miembro.usuario_id),
            'nombre_usuario': usuario.nombre_usuario if miembro.usuario_id == usuario.id else None,
            'puede_aportar': miembro.puede_aportar,
            'puede_modificar_cola': miembro.puede_modificar_cola,
            'estado': miembro.estado,
            'conectado': participacion is not None,
            'orden_ingreso': participacion.orden_ingreso if participacion else None,
        })

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


def leer_clave_idempotencia(valor):
    try:
        return uuid.UUID(valor or '')
    except ValueError:
        raise ErrorApi(400, 'DATOS_INVALIDOS', 'Falta la cabecera Idempotency-Key o no es un UUID válido.')