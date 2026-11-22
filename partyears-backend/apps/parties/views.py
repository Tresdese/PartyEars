import re
import uuid
from rest_framework.response import Response
from rest_framework.views import APIView
from .errores import ErrorApi, datos_invalidos
from .servicios import (cambiar_permisos, consultar_party, crear_party, expulsar_miembro,
                        finalizar_party, leer_clave_idempotencia, party_actual,
                        rehabilitar_miembro, salir_party, transferir_anfitrion,
                        unirse_party)

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


class PartyView(APIView):
    """GET /api/v1/party/parties/{party_id} (RF-09)."""

    def get(self, request, party_id):
        return Response(consultar_party(request.user, party_id))


def validar_permisos(cuerpo):
    if not isinstance(cuerpo, dict):
        raise datos_invalidos('El cuerpo de la petición debe ser un objeto JSON.')
    for campo in ('puede_aportar', 'puede_modificar_cola'):
        if not isinstance(cuerpo.get(campo), bool):
            raise datos_invalidos('Indica cada permiso como true o false.', campo,
                                  ['Debe ser true o false.'])
    return cuerpo['puede_aportar'], cuerpo['puede_modificar_cola'], validar_version(cuerpo)


def validar_version(cuerpo):
    version = cuerpo.get('version_esperada') if isinstance(cuerpo, dict) else None
    # bool excluded on purpose: in Python True is an int, and JSON true is not a version.
    if not isinstance(version, int) or isinstance(version, bool) or version < 0:
        raise datos_invalidos('Falta la versión de la party que estás viendo.',
                              'version_esperada', ['Debe ser un entero.'])
    return version


class PermisosView(APIView):
    """PUT /api/v1/party/parties/{party_id}/miembros/{usuario_id}/permisos (RF-17, RF-18)."""

    def put(self, request, party_id, usuario_id):
        clave = leer_clave_idempotencia(request.headers.get('Idempotency-Key'))
        puede_aportar, puede_modificar_cola, version = validar_permisos(request.data)
        resultado, codigo_http = cambiar_permisos(request.user, party_id, usuario_id,
                                                  puede_aportar, puede_modificar_cola, version,
                                                  clave)
        return Response(resultado, status=codigo_http)


class SalirView(APIView):
    """POST /api/v1/party/parties/{party_id}/salir (RF-19, RF-22)."""

    def post(self, request, party_id):
        clave = leer_clave_idempotencia(request.headers.get('Idempotency-Key'))
        _, codigo_http = salir_party(request.user, party_id, clave)
        return Response(status=codigo_http)


class FinalizarView(APIView):
    """POST /api/v1/party/parties/{party_id}/finalizar (RF-20)."""

    def post(self, request, party_id):
        clave = leer_clave_idempotencia(request.headers.get('Idempotency-Key'))
        _, codigo_http = finalizar_party(request.user, party_id, clave)
        return Response(status=codigo_http)


class ExpulsarView(APIView):
    """POST /api/v1/party/parties/{party_id}/miembros/{usuario_id}/expulsar (RF-30)."""
    servicio = staticmethod(expulsar_miembro)

    def post(self, request, party_id, usuario_id):
        clave = leer_clave_idempotencia(request.headers.get('Idempotency-Key'))
        version = validar_version(request.data)
        _, codigo_http = self.servicio(request.user, party_id, usuario_id, version, clave)
        return Response(status=codigo_http)


class RehabilitarView(ExpulsarView):
    """POST /api/v1/party/parties/{party_id}/miembros/{usuario_id}/rehabilitar (RF-30)."""
    servicio = staticmethod(rehabilitar_miembro)


class AnfitrionView(APIView):
    """POST /api/v1/party/parties/{party_id}/anfitrion (RF-31)."""

    def post(self, request, party_id):
        clave = leer_clave_idempotencia(request.headers.get('Idempotency-Key'))
        version = validar_version(request.data)
        try:
            destinatario = uuid.UUID(str(request.data.get('usuario_id')))
        except ValueError:
            raise datos_invalidos('Elige a quién pasarle el cargo.', 'usuario_id',
                                  ['Debe ser un UUID.'])
        _, codigo_http = transferir_anfitrion(request.user, party_id, destinatario, version, clave)
        return Response(status=codigo_http)
