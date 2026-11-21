import re
import uuid
from rest_framework.response import Response
from rest_framework.views import APIView
from .errores import ErrorApi, datos_invalidos
from .servicios import crear_party, leer_clave_idempotencia, party_actual, unirse_party

FORMATO_CODIGO = re.compile(r'^[A-Z0-9]{6}$')

LONGITUD_MAXIMA_NOMBRE = 100

def validar_creacion(cuerpo):
    if not isinstance(cuerpo, dict):
        raise datos_invalidos('El cuerpo de la petición debe ser un objeto JSON.')

    nombre = cuerpo.get('nombre')
    nombre = nombre.strip() if isinstance(nombre, str) else ''
    if not nombre:
        raise datos_invalidos('Ponle un nombre a la party.', 'nombre', ['Este campo es obligatorio.'])
    if len(nombre) > LONGITUD_MAXIMA_NOMBRE:
        raise datos_invalidos('El nombre de la party es demasiado largo.', 'nombre', [f'Máximo {LONGITUD_MAXIMA_NOMBRE} caracteres.'])

    recurso = cuerpo.get('recurso_audio_id_inicial')
    if recurso is not None:
        try:
            recurso = str(uuid.UUID(str(recurso)))
        except ValueError:
            raise datos_invalidos('La canción inicial no es válida.', 'recurso_audio_id_inicial', ['Debe ser un UUID o null.'])

    return nombre, recurso

class PartiesView(APIView):
    """POST /api/v1/party/parties (RF-06, RF-07)."""

    def post(self, request):
        clave = leer_clave_idempotencia(request.headers.get('Idempotency-Key'))
        nombre, recurso = validar_creacion(request.data)
        estado, codigo_http = crear_party(request.user, nombre, recurso, clave)
        return Response(estado, status=codigo_http)


class PartyActualView(APIView):
    """GET /api/v1/party/parties/actual."""

    def get(self, request):
        estado = party_actual(request.user)
        if estado is None:
            return Response(status=204)
        return Response(estado)


def validar_codigo(cuerpo):
    codigo = cuerpo.get('codigo') if isinstance(cuerpo, dict) else None
    if not isinstance(codigo, str):
        raise datos_invalidos('Escribe el código de la party.', 'codigo',
                              ['Este campo es obligatorio.'])
    # Normalizing instead of rejecting: people type the code by hand, with lowercase or spaces.
    codigo = codigo.strip().upper()
    if not FORMATO_CODIGO.match(codigo):
        raise ErrorApi(404, 'CODIGO_INVALIDO', 'Ese código no corresponde a ninguna party.')
    return codigo


class UnirseView(APIView):
    """POST /api/v1/party/parties/unirse (RF-08, RF-36)."""

    def post(self, request):
        clave = leer_clave_idempotencia(request.headers.get('Idempotency-Key'))
        codigo = validar_codigo(request.data)
        estado, codigo_http = unirse_party(request.user, codigo, clave)
        return Response(estado, status=codigo_http)
