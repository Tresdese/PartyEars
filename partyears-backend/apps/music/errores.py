from rest_framework import exceptions
from rest_framework.response import Response
from rest_framework.views import exception_handler


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


def manejar_excepcion(exc, contexto):
    if isinstance(exc, ErrorApi):
        return Response(exc.cuerpo(), status=exc.estado)

    if isinstance(exc, (exceptions.AuthenticationFailed, exceptions.NotAuthenticated)):
        return Response(
            {
                'codigo': 'TOKEN_INVALIDO',
                'mensaje': 'Tu sesión ya no es válida. Inicia sesión de nuevo.',
                'detalles': None,
            },
            status=401,
        )

    respuesta = exception_handler(exc, contexto)
    if respuesta is None:
        return None

    codigos = {404: 'NO_ENCONTRADO', 405: 'METODO_NO_PERMITIDO'}
    respuesta.data = {
        'codigo': codigos.get(respuesta.status_code, 'ERROR'),
        'mensaje': 'No se pudo completar la operación.',
        'detalles': None,
    }
    return respuesta
