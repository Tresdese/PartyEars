import io
import uuid
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from django.test import SimpleTestCase

from apps.musicqueue.cliente_party import consultar_party
from apps.parties.errores import ErrorApi


def error_http(codigo, cuerpo):
    return HTTPError('http://party', codigo, 'error', {}, io.BytesIO(cuerpo.encode()))


class ClientePartyTests(SimpleTestCase):

    def consultar_con(self, efecto):
        with patch('apps.musicqueue.cliente_party.urlopen', side_effect=efecto):
            with self.assertRaises(ErrorApi) as error:
                consultar_party('token', uuid.uuid4())
        return error.exception.estado, error.exception.codigo

    def test_error_del_contrato_pasa_igual(self):
        cuerpo = '{"codigo": "NO_ES_MIEMBRO", "mensaje": "No estás dentro."}'
        self.assertEqual(self.consultar_con(error_http(403, cuerpo)), (403, 'NO_ES_MIEMBRO'))

    def test_error_500_de_party_es_servicio_no_disponible(self):
        cuerpo = '{"codigo": "ERROR", "mensaje": "x"}'
        self.assertEqual(self.consultar_con(error_http(500, cuerpo)),
                         (503, 'SERVICIO_NO_DISPONIBLE'))

    def test_respuesta_que_no_es_json_es_servicio_no_disponible(self):
        self.assertEqual(self.consultar_con(error_http(404, '<html>')),
                         (503, 'SERVICIO_NO_DISPONIBLE'))

    def test_party_apagado_es_servicio_no_disponible(self):
        self.assertEqual(self.consultar_con(URLError('refused')), (503, 'SERVICIO_NO_DISPONIBLE'))

    def test_party_que_tarda_es_servicio_no_disponible(self):
        self.assertEqual(self.consultar_con(TimeoutError()), (503, 'SERVICIO_NO_DISPONIBLE'))
