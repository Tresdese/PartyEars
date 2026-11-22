import hashlib
import secrets
import uuid
from datetime import timedelta

import jwt
from django.conf import settings
from django.utils import timezone
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

from .models import Sesion

DURACION_TOKEN_ACCESO = timedelta(minutes=5)
DURACION_TOKEN_RENOVACION = timedelta(days=7)


class UsuarioToken:
    """Representación del usuario autenticado extraída del JWT."""

    is_authenticated = True
    is_anonymous = False

    def __init__(self, id, nombre_usuario, sesion_id):
        self.id = id
        self.nombre_usuario = nombre_usuario
        self.sesion_id = sesion_id


def hashear_token_renovacion(token_plano: str) -> str:
    return hashlib.sha256(token_plano.encode('utf-8')).hexdigest()


def generar_token_renovacion() -> str:
    return secrets.token_urlsafe(48)


def emitir_token_acceso(usuario, sesion_id: uuid.UUID, ahora=None):
    ahora = ahora or timezone.now()
    expira = ahora + DURACION_TOKEN_ACCESO
    payload = {
        'sub': str(usuario.id),
        'nombre_usuario': usuario.nombre_usuario,
        'sid': str(sesion_id),
        'iat': int(ahora.timestamp()),
        'exp': int(expira.timestamp()),
    }
    token = jwt.encode(payload, settings.JWT_CLAVE_PRIVADA, algorithm='RS256')
    return token, expira


class JWTAuthentication(BaseAuthentication):
    def authenticate_header(self, request):
        return 'Bearer'

    def authenticate(self, request):
        cabecera = request.headers.get('Authorization', '')
        if not cabecera:
            return None

        partes = cabecera.split()
        if len(partes) != 2 or partes[0].lower() != 'bearer':
            raise AuthenticationFailed()

        try:
            contenido = jwt.decode(
                partes[1],
                settings.JWT_CLAVE_PUBLICA,
                algorithms=['RS256'],
                options={'require': ['exp', 'sub']},
            )
            usuario_id = uuid.UUID(str(contenido['sub']))
            sesion_id = uuid.UUID(str(contenido['sid'])) if contenido.get('sid') else None
        except (jwt.PyJWTError, ValueError):
            raise AuthenticationFailed()

        if sesion_id is not None:
            sesion_activa = Sesion.objects.filter(
                id=sesion_id,
                usuario_id=usuario_id,
                revocada_en__isnull=True,
                usuario__activo=True,
            ).exists()
            if not sesion_activa:
                raise AuthenticationFailed()

        return UsuarioToken(usuario_id, contenido.get('nombre_usuario'), sesion_id), partes[1]
