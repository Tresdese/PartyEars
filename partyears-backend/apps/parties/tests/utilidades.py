import time
import uuid

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from django.db import connection
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.parties.models import AnfitrionParty, MiembroParty, ParticipacionParty, Party


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


def crear_party_en_bd(anfitrion_id):
    """Party mínima con su anfitrión conectado, sin pasar por la API."""
    party = Party.objects.create(nombre='Viernes', creada_por=anfitrion_id, version=1)
    MiembroParty.objects.create(party=party, usuario_id=anfitrion_id, puede_aportar=True,
                                puede_modificar_cola=True)
    AnfitrionParty.objects.create(party=party, usuario_id=anfitrion_id)
    ParticipacionParty.objects.create(party=party, usuario_id=anfitrion_id)
    return party.id


def agregar_miembro(party_id, usuario_id, esta_conectado=True):
    MiembroParty.objects.create(party_id=party_id, usuario_id=usuario_id)
    if esta_conectado:
        ParticipacionParty.objects.create(party_id=party_id, usuario_id=usuario_id)


def vaciar_tablas_party():
    # TRUNCATE instead of relying on Django: it does not flush unmanaged tables between tests.
    with connection.cursor() as cursor:
        cursor.execute('TRUNCATE party.party, party.miembro_party, party.anfitrion_party, '
                       'party.participacion_party, party.invitacion_party, '
                       'party.operacion_confirmada, party.evento_salida CASCADE')
