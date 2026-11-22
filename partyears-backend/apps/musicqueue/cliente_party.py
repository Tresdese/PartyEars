import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings

from apps.parties.errores import ErrorApi

TIEMPO_ESPERA_S = 3
# Errors from party that mean something to the user; anything else is party being down.
ERRORES_DE_PARTY = (401, 403, 404, 410)


def _servicio_no_disponible():
    return ErrorApi(503, 'SERVICIO_NO_DISPONIBLE',
                    'No se pudo comprobar la party. Intenta de nuevo en unos segundos.')


def consultar_party(token, party_id):
    """Estado de la party (contrato 4.3) visto por el dueño del token."""
    # TODO(T-34): synchronous call instead of the replica fed by party.eventos that contract 5.2
    # describes; there is no outbox relay or RabbitMQ consumer yet, so for the MVP queue asks
    # party on every operation and fails with 503 while party is down.
    peticion = Request(f'{settings.PARTY_URL}/api/v1/party/parties/{party_id}',
                       headers={'Authorization': f'Bearer {token}'})
    try:
        with urlopen(peticion, timeout=TIEMPO_ESPERA_S) as respuesta:
            return json.load(respuesta)
    except HTTPError as error:
        if error.code not in ERRORES_DE_PARTY:
            raise _servicio_no_disponible()
        try:
            cuerpo = json.load(error)
            codigo, mensaje = cuerpo['codigo'], cuerpo['mensaje']
        except (ValueError, KeyError, TypeError):
            raise _servicio_no_disponible()
        raise ErrorApi(error.code, codigo, mensaje)
    except (URLError, TimeoutError, ValueError):
        raise _servicio_no_disponible()
