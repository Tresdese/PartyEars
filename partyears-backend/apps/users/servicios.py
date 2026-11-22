import uuid
from datetime import timezone as dt_timezone

from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import IntegrityError, transaction
from django.utils import timezone

from .autenticacion import (
    DURACION_TOKEN_RENOVACION,
    emitir_token_acceso,
    generar_token_renovacion,
    hashear_token_renovacion,
)
from .errores import ErrorApi, datos_invalidos
from .models import Sesion, Usuario

LONGITUD_MINIMA_CONTRASENA = 10


def formatear_fecha(dt) -> str:
    return dt.astimezone(dt_timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'


def _crear_sesion_y_tokens(usuario: Usuario, ahora=None) -> dict:
    ahora = ahora or timezone.now()
    token_renovacion = generar_token_renovacion()
    sesion = Sesion.objects.create(
        usuario=usuario,
        token_renovacion_hash=hashear_token_renovacion(token_renovacion),
        creada_en=ahora,
        expira_en=ahora + DURACION_TOKEN_RENOVACION,
    )
    token_acceso, expira_acceso = emitir_token_acceso(usuario, sesion.id, ahora=ahora)
    return {
        'token_acceso': token_acceso,
        'token_renovacion': token_renovacion,
        'expira_en': formatear_fecha(expira_acceso),
        'usuario': {
            'id': str(usuario.id),
            'nombre_usuario': usuario.nombre_usuario,
        },
    }


def registrar_usuario(datos: dict) -> dict:
    if not isinstance(datos, dict):
        raise datos_invalidos('El cuerpo de la petición debe ser un objeto JSON.')

    errores = {}

    nombre_raw = datos.get('nombre_usuario')
    correo_raw = datos.get('correo')
    contrasena = datos.get('contrasena')
    confirmacion = datos.get('confirmacion')

    nombre_usuario = nombre_raw.strip() if isinstance(nombre_raw, str) else ''
    correo = correo_raw.strip().lower() if isinstance(correo_raw, str) else ''

    if not nombre_usuario:
        errores['nombre_usuario'] = ['Este campo es obligatorio.']
    elif len(nombre_usuario) > 40:
        errores['nombre_usuario'] = ['No puede exceder 40 caracteres.']

    if not correo:
        errores['correo'] = ['Este campo es obligatorio.']
    else:
        try:
            validate_email(correo)
        except ValidationError:
            errores['correo'] = ['Introduce un correo electrónico válido.']

    if not isinstance(contrasena, str) or len(contrasena) < LONGITUD_MINIMA_CONTRASENA:
        errores['contrasena'] = [
            f'La contraseña debe tener al menos {LONGITUD_MINIMA_CONTRASENA} caracteres.'
        ]

    if not isinstance(confirmacion, str) or confirmacion != contrasena:
        errores['confirmacion'] = ['Las contraseñas no coinciden.']

    if errores:
        raise datos_invalidos('Revisa los datos del registro.', detalles=errores)

    if Usuario.objects.filter(correo__iexact=correo).exists():
        raise ErrorApi(
            409,
            'DUPLICADO',
            'El correo ya está registrado.',
            detalles={'correo': ['Ya está registrado.']},
        )

    if Usuario.objects.filter(nombre_usuario__iexact=nombre_usuario).exists():
        raise ErrorApi(
            409,
            'DUPLICADO',
            'El nombre de usuario ya está en uso.',
            detalles={'nombre_usuario': ['Ya está en uso.']},
        )

    ahora = timezone.now()
    usuario = Usuario(
        nombre_usuario=nombre_usuario,
        correo=correo,
        activo=True,
        creado_en=ahora,
        actualizado_en=ahora,
    )
    usuario.establecer_contrasena(contrasena)

    try:
        usuario.save()
    except IntegrityError as exc:
        mensaje_bd = str(exc).lower()
        if 'correo' in mensaje_bd:
            raise ErrorApi(
                409,
                'DUPLICADO',
                'El correo ya está registrado.',
                detalles={'correo': ['Ya está registrado.']},
            )
        raise ErrorApi(
            409,
            'DUPLICADO',
            'El nombre de usuario ya está en uso.',
            detalles={'nombre_usuario': ['Ya está en uso.']},
        )

    return {
        'id': str(usuario.id),
        'nombre_usuario': usuario.nombre_usuario,
        'correo': usuario.correo,
        'creado_en': formatear_fecha(usuario.creado_en),
    }


def iniciar_sesion(datos: dict) -> dict:
    if not isinstance(datos, dict):
        raise datos_invalidos('El cuerpo de la petición debe ser un objeto JSON.')

    correo_raw = datos.get('correo')
    contrasena = datos.get('contrasena')

    errores = {}
    if not isinstance(correo_raw, str) or not correo_raw.strip():
        errores['correo'] = ['Este campo es obligatorio.']
    if not isinstance(contrasena, str) or not contrasena:
        errores['contrasena'] = ['Este campo es obligatorio.']
    if errores:
        raise datos_invalidos('Debes proporcionar correo y contraseña.', detalles=errores)

    usuario = Usuario.objects.filter(correo__iexact=correo_raw.strip()).first()
    if usuario is None or not usuario.verificar_contrasena(contrasena):
        raise ErrorApi(401, 'CREDENCIALES_INVALIDAS', 'Correo o contraseña incorrectos.')

    if not usuario.activo:
        raise ErrorApi(403, 'CUENTA_INACTIVA', 'Tu cuenta se encuentra inactiva.')

    return _crear_sesion_y_tokens(usuario)


@transaction.atomic
def renovar_sesion(datos: dict) -> dict:
    if not isinstance(datos, dict):
        raise datos_invalidos('El cuerpo de la petición debe ser un objeto JSON.')

    token_renovacion = datos.get('token_renovacion')
    if not isinstance(token_renovacion, str) or not token_renovacion.strip():
        raise datos_invalidos(
            'El token de renovación es obligatorio.',
            detalles={'token_renovacion': ['Este campo es obligatorio.']},
        )

    ahora = timezone.now()
    sesion = (
        Sesion.objects.select_related('usuario')
        .select_for_update()
        .filter(token_renovacion_hash=hashear_token_renovacion(token_renovacion.strip()))
        .first()
    )

    if sesion is None or sesion.revocada_en is not None or sesion.expira_en <= ahora:
        raise ErrorApi(401, 'TOKEN_INVALIDO', 'El token de renovación no es válido o ha expirado.')

    if not sesion.usuario.activo:
        raise ErrorApi(403, 'CUENTA_INACTIVA', 'Tu cuenta se encuentra inactiva.')

    sesion.revocada_en = ahora
    sesion.save(update_fields=['revocada_en'])

    return _crear_sesion_y_tokens(sesion.usuario, ahora=ahora)


@transaction.atomic
def cerrar_sesion(usuario_token, datos: dict) -> None:
    if not isinstance(datos, dict):
        raise datos_invalidos('El cuerpo de la petición debe ser un objeto JSON.')

    token_renovacion = datos.get('token_renovacion')
    if not isinstance(token_renovacion, str) or not token_renovacion.strip():
        raise datos_invalidos(
            'El token de renovación es obligatorio.',
            detalles={'token_renovacion': ['Este campo es obligatorio.']},
        )

    ahora = timezone.now()
    sesion = (
        Sesion.objects.select_for_update()
        .filter(
            token_renovacion_hash=hashear_token_renovacion(token_renovacion.strip()),
            usuario_id=usuario_token.id,
        )
        .first()
    )

    if sesion is None or sesion.revocada_en is not None:
        raise ErrorApi(401, 'TOKEN_INVALIDO', 'La sesión no es válida o ya fue cerrada.')

    sesion.revocada_en = ahora
    sesion.save(update_fields=['revocada_en'])

    if usuario_token.sesion_id and usuario_token.sesion_id != sesion.id:
        Sesion.objects.filter(
            id=usuario_token.sesion_id,
            usuario_id=usuario_token.id,
            revocada_en__isnull=True,
        ).update(revocada_en=ahora)


def consultar_usuarios_por_ids(ids_param: str) -> list:
    if not ids_param or not ids_param.strip():
        return []

    uuids = []
    for fragmento in ids_param.split(','):
        fragmento = fragmento.strip()
        if not fragmento:
            continue
        try:
            uuids.append(uuid.UUID(fragmento))
        except ValueError:
            raise datos_invalidos(
                'Uno o más identificadores de usuario no son UUID válidos.',
                detalles={'ids': ['Formato de UUID inválido.']},
            )

    if not uuids:
        return []

    usuarios = Usuario.objects.filter(id__in=uuids).order_by('nombre_usuario')
    return [{'id': str(u.id), 'nombre_usuario': u.nombre_usuario} for u in usuarios]
