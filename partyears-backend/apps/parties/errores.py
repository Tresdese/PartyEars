import logging
import uuid

from django.conf import settings
from django.db import DatabaseError
from django.utils.module_loading import import_string
from rest_framework import exceptions
from rest_framework.response import Response
from rest_framework.views import exception_handler

logger = logging.getLogger(__name__)

class ErrorApi(Exception):
    """Error con el formato del contrato (1.4): código, mensaje y detalles opcionales."""

    def __init__(self, estado, codigo, mensaje, detalles=None):
        super().__init__(mensaje)
        self.estado = estado
        self.codigo = codigo
        self.mensaje = mensaje
        self.detalles = detalles

    def cuerpo(self):
        cuerpo = {'codigo': self.codigo, 'mensaje': self.mensaje}
        if self.detalles is not None:
            cuerpo['detalles'] = self.detalles
        return cuerpo

def datos_invalidos(mensaje, campo=None, errores=None):
    detalles = {campo: errores} if campo else None
    return ErrorApi(400, 'DATOS_INVALIDOS', mensaje, detalles)

def _registrar_rechazo(error, contexto):
    """RF-34 asks logs to show rejections too. Only views that declare `operaciones` and act
    on a party are recorded: the record hangs from that party or its cola."""
    request = contexto['request']
    operacion = getattr(contexto['view'], 'operaciones', {}).get(request.method)
    party_id = contexto['kwargs'].get('party_id')
    if operacion is None or party_id is None or request.user is None:
        return
    try:
        clave = uuid.UUID(request.headers.get('Idempotency-Key', ''))
    except ValueError:
        clave = None
    try:
        import_string(settings.REGISTRAR_RECHAZO)(request.user.id, party_id, operacion, error,
                                                  clave)
    except DatabaseError:
        # Logging instead of failing: the client must still get its real error.
        logger.exception('No se pudo registrar el rechazo de %s', operacion)


def manejar_excepcion(exc, contexto):
    if isinstance(exc, ErrorApi):
        _registrar_rechazo(exc, contexto)
        return Response(exc.cuerpo(), status=exc.estado)

    if isinstance(exc, (exceptions.AuthenticationFailed, exceptions.NotAuthenticated)):
        return Response({'codigo': 'TOKEN_INVALIDO', 'mensaje': 'Tu sesión ya no es válida. Inicia sesión de nuevo.'}, status=401)

    if isinstance(exc, (exceptions.ParseError, exceptions.UnsupportedMediaType)):
        return Response({'codigo': 'DATOS_INVALIDOS', 'mensaje': 'El cuerpo de la petición no es un JSON válido.'}, status=400)

    respuesta = exception_handler(exc, contexto)
    if respuesta is None:
        return None

    codigos = {404: 'NO_ENCONTRADO', 405: 'METODO_NO_PERMITIDO'}
    respuesta.data = {'codigo': codigos.get(respuesta.status_code, 'ERROR'), 'mensaje': 'No se pudo completar la operación.'}
    return respuesta