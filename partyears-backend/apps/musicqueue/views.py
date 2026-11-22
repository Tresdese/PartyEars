import uuid

from rest_framework.response import Response
from rest_framework.views import APIView

from apps.parties.errores import datos_invalidos
from .cliente_party import consultar_party
from .servicios import (agregar_elemento, consultar_cola, leer_clave_idempotencia,
                        reordenar_elemento, retirar_elemento)


def _es_entero(valor):
    # bool is excluded on purpose: in Python True is an int, and JSON true is not a version.
    return isinstance(valor, int) and not isinstance(valor, bool)


def leer_objeto(cuerpo):
    if not isinstance(cuerpo, dict):
        raise datos_invalidos('El cuerpo de la petición debe ser un objeto JSON.')
    return cuerpo


def leer_uuid(valor, campo, mensaje):
    try:
        return str(uuid.UUID(str(valor)))
    except ValueError:
        raise datos_invalidos(mensaje, campo, ['Debe ser un UUID.'])


def leer_version(valor):
    if isinstance(valor, str) and valor.isdigit():
        valor = int(valor)
    if not _es_entero(valor) or valor < 0:
        raise datos_invalidos('Falta la versión de la cola que estás viendo.',
                              'version_esperada', ['Debe ser un entero.'])
    return valor


class ColaView(APIView):
    """GET /api/v1/queue/parties/{party_id}/cola."""

    def get(self, request, party_id):
        consultar_party(request.auth, party_id)
        return Response(consultar_cola(party_id))


class ElementosView(APIView):
    """POST /api/v1/queue/parties/{party_id}/cola/elementos (RF-11)."""

    def post(self, request, party_id):
        clave = leer_clave_idempotencia(request.headers.get('Idempotency-Key'))
        cuerpo = leer_objeto(request.data)
        recurso = leer_uuid(cuerpo.get('recurso_audio_id'), 'recurso_audio_id',
                            'La canción no es válida.')
        party = consultar_party(request.auth, party_id)
        estado, codigo_http = agregar_elemento(party, request.user.id, recurso, clave)
        return Response(estado, status=codigo_http)


class ElementoView(APIView):
    """PATCH y DELETE /api/v1/queue/parties/{party_id}/cola/elementos/{elemento_id}."""

    def patch(self, request, party_id, elemento_id):
        clave = leer_clave_idempotencia(request.headers.get('Idempotency-Key'))
        cuerpo = leer_objeto(request.data)
        posicion = cuerpo.get('nueva_posicion')
        if not _es_entero(posicion) or posicion < 1:
            raise datos_invalidos('La nueva posición no es válida.', 'nueva_posicion',
                                  ['Debe ser un entero desde 1.'])
        version = leer_version(cuerpo.get('version_esperada'))
        party = consultar_party(request.auth, party_id)
        estado, codigo_http = reordenar_elemento(party, request.user.id, elemento_id, posicion,
                                                 version, clave)
        return Response(estado, status=codigo_http)

    def delete(self, request, party_id, elemento_id):
        clave = leer_clave_idempotencia(request.headers.get('Idempotency-Key'))
        version = leer_version(request.query_params.get('version_esperada'))
        party = consultar_party(request.auth, party_id)
        estado, codigo_http = retirar_elemento(party, request.user.id, elemento_id, version,
                                               clave)
        return Response(estado, status=codigo_http)
