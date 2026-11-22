import uuid

import jwt
from django.conf import settings
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed


class UsuarioToken:
    """Usuario extraído del JWT emitido por auth."""

    is_authenticated = True
    is_anonymous = False

    def __init__(self, id, nombre_usuario, sesion_id):
        self.id = id
        self.nombre_usuario = nombre_usuario
        self.sesion_id = sesion_id


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
        except (jwt.PyJWTError, ValueError):
            raise AuthenticationFailed()

        return UsuarioToken(usuario_id, contenido.get('nombre_usuario'), contenido.get('sid')), partes[1]
