import time
import uuid
from unittest.mock import patch

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from django.db import connection
from django.test import TestCase, TransactionTestCase, override_settings
from rest_framework.test import APIClient

# A key pair of its own instead of party's test helpers: those import party's models, which
# do not exist in the queue service.
_PRIVADA = rsa.generate_private_key(public_exponent=65537, key_size=2048)
CLAVE_PUBLICA = _PRIVADA.public_key().public_bytes(
    serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode()


def hacer_token(usuario_id):
    ahora = int(time.time())
    return jwt.encode({'sub': str(usuario_id), 'iat': ahora, 'exp': ahora + 300}, _PRIVADA,
                      algorithm='RS256')


def miembro(usuario_id, puede_aportar=False, puede_modificar_cola=False):
    return {'usuario_id': str(usuario_id), 'puede_aportar': puede_aportar,
            'puede_modificar_cola': puede_modificar_cola, 'estado': 'habilitado',
            'conectado': True}


class BaseCola:
    """party simulada: anfitrión, un oyente sin permisos y miembros con cada permiso."""

    def setUp(self):
        self.cliente = APIClient()
        self.party_id = uuid.uuid4()
        self.anfitrion_id = uuid.uuid4()
        self.oyente_id = uuid.uuid4()
        self.aportador_id = uuid.uuid4()
        self.modificador_id = uuid.uuid4()
        self.party = {
            'id': str(self.party_id),
            'anfitrion_id': str(self.anfitrion_id),
            'miembros': [miembro(self.anfitrion_id, True, True), miembro(self.oyente_id),
                         miembro(self.aportador_id, puede_aportar=True),
                         miembro(self.modificador_id, puede_modificar_cola=True)],
        }
        simulada = patch('apps.musicqueue.views.consultar_party', side_effect=self.simular_party)
        self.consultar_party = simulada.start()
        self.addCleanup(simulada.stop)
        self.url = f'/api/v1/queue/parties/{self.party_id}/cola'

    def simular_party(self, token, party_id):
        return self.party

    def cabeceras(self, usuario_id, clave=None):
        return {'HTTP_AUTHORIZATION': f'Bearer {hacer_token(usuario_id)}',
                'HTTP_IDEMPOTENCY_KEY': str(clave or uuid.uuid4())}

    def consultar(self, usuario_id=None):
        return self.cliente.get(self.url, **self.cabeceras(usuario_id or self.anfitrion_id))

    def agregar(self, usuario_id=None, recurso=None, clave=None):
        return self.cliente.post(f'{self.url}/elementos',
                                 {'recurso_audio_id': str(recurso or uuid.uuid4())},
                                 format='json',
                                 **self.cabeceras(usuario_id or self.anfitrion_id, clave))

    def reordenar(self, elemento_id, posicion, version, usuario_id=None, clave=None):
        return self.cliente.patch(f'{self.url}/elementos/{elemento_id}',
                                  {'nueva_posicion': posicion, 'version_esperada': version},
                                  format='json',
                                  **self.cabeceras(usuario_id or self.anfitrion_id, clave))

    def retirar(self, elemento_id, version, usuario_id=None, clave=None):
        url = f'{self.url}/elementos/{elemento_id}?version_esperada={version}'
        return self.cliente.delete(url, **self.cabeceras(usuario_id or self.anfitrion_id, clave))

    def verificar_error(self, respuesta, estado, codigo):
        self.assertEqual((respuesta.status_code, respuesta.json()['codigo']), (estado, codigo))

    def ids_pendientes(self, estado):
        return [e['id'] for e in estado['pendientes']]


@override_settings(JWT_CLAVE_PUBLICA=CLAVE_PUBLICA)
class PruebasCola(BaseCola, TestCase):
    pass


@override_settings(JWT_CLAVE_PUBLICA=CLAVE_PUBLICA)
class PruebasColaConcurrentes(BaseCola, TransactionTestCase):

    def tearDown(self):
        # TRUNCATE instead of relying on Django: it does not flush unmanaged tables.
        with connection.cursor() as cursor:
            cursor.execute('TRUNCATE queue.cola, queue.elemento_cola, '
                           'queue.operacion_confirmada, queue.evento_salida CASCADE')
