import time
import uuid

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from django.test import TestCase, override_settings
from rest_framework.test import APIClient


def _generar_par_de_claves():
    privada = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    publica = privada.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode()
    return privada, publica


CLAVE_PRIVADA, CLAVE_PUBLICA = _generar_par_de_claves()
OTRA_CLAVE_PRIVADA, _ = _generar_par_de_claves()


def hacer_token(usuario_id=None, clave=CLAVE_PRIVADA, vence_en=300, nombre_usuario='mariana'):
    ahora = int(time.time())
    datos = {
        'sub': str(usuario_id or uuid.uuid4()),
        'nombre_usuario': nombre_usuario,
        'sid': str(uuid.uuid4()),
        'iat': ahora,
        'exp': ahora + vence_en,
    }
    return jwt.encode(datos, clave, algorithm='RS256')


@override_settings(JWT_CLAVE_PUBLICA=CLAVE_PUBLICA)
class PruebasBase(TestCase):
    URL = '/api/v1/party/parties'

    def setUp(self):
        self.cliente = APIClient()

    def crear(self, usuario_id=None, cuerpo=None, clave=None, nombre_usuario='mariana',
              token=None):
        usuario_id = usuario_id or uuid.uuid4()
        token = token or hacer_token(usuario_id, nombre_usuario=nombre_usuario)
        cabeceras = {'HTTP_AUTHORIZATION': f'Bearer {token}'}
        if clave != 'sin_clave':
            cabeceras['HTTP_IDEMPOTENCY_KEY'] = str(clave or uuid.uuid4())
        cuerpo = {'nombre': 'Viernes'} if cuerpo is None else cuerpo
        return self.cliente.post(self.URL, cuerpo, format='json', **cabeceras)

    def consultar_actual(self, usuario_id, nombre_usuario='mariana'):
        token = hacer_token(usuario_id, nombre_usuario=nombre_usuario)
        return self.cliente.get(self.URL + '/actual', HTTP_AUTHORIZATION=f'Bearer {token}')
