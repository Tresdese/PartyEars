"""
Pruebas de T-30: WebSocket de party autenticado por token, un grupo por party.
Contrato: docs/contrato-api.md, secciones 1.3 y 7.

Correr (no necesitan base de datos ni Redis):
    DJANGO_SETTINGS_MODULE=config.settings.party python manage.py test apps.parties

Lo que estas pruebas esperan que exista:
    apps/parties/routing.py   websocket_urlpatterns con 'ws/v1/party/parties/<uuid:party_id>/'
    apps/parties/eventos.py   async def publicar(party_id, tipo, datos, version=None)
                              manda el evento a todos los clientes autenticados de esa party
    settings.JWT_CLAVE_PUBLICA     clave pública RS256 de auth, en PEM
    settings.WS_TIEMPO_AUTENTICAR  segundos para mandar 'autenticar' (5 según el contrato)

Fuera de T-30 (llegan con T-33): 4003 no es miembro, 4004 la party no existe, 4010 finalizó,
y la 'version' real en 'autenticado'.
"""

import time
import uuid
from unittest import IsolatedAsyncioTestCase

import jwt
from channels.routing import URLRouter
from channels.testing import WebsocketCommunicator
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from django.test import override_settings

from apps.parties.eventos import publicar
from apps.parties.routing import websocket_urlpatterns


def _par_de_claves():
    privada = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    publica = privada.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode()
    return privada, publica


CLAVE_PRIVADA, CLAVE_PUBLICA = _par_de_claves()
OTRA_CLAVE_PRIVADA, _ = _par_de_claves()  # simula un token que no firmó auth


def token(clave=CLAVE_PRIVADA, vence_en=300, **cambios):
    ahora = int(time.time())
    datos = {
        'sub': str(uuid.uuid4()),
        'nombre_usuario': 'darlington',
        'sid': str(uuid.uuid4()),
        'iat': ahora,
        'exp': ahora + vence_en,
    }
    datos.update(cambios)
    datos = {k: v for k, v in datos.items() if v is not None}  # None = quitar el campo
    return jwt.encode(datos, clave, algorithm='RS256')


# IsolatedAsyncioTestCase y no SimpleTestCase: Django no ejecuta asyncTearDown, y sin él quedan
# conexiones abiertas entre pruebas.
class WebSocketPartyTests(IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        ajustes = override_settings(
            JWT_CLAVE_PUBLICA=CLAVE_PUBLICA,
            WS_TIEMPO_AUTENTICAR=0.3,
            CHANNEL_LAYERS={'default': {'BACKEND': 'channels.layers.InMemoryChannelLayer'}},
        )
        ajustes.enable()
        self.addCleanup(ajustes.disable)
        self.party_id = uuid.uuid4()
        self.abiertos = []

    async def asyncTearDown(self):
        for cliente in self.abiertos:
            await cliente.disconnect()

    # --- ayudantes ---

    async def conectar(self, party_id=None):
        cliente = WebsocketCommunicator(
            URLRouter(websocket_urlpatterns), f'/ws/v1/party/parties/{party_id or self.party_id}/'
        )
        conectado, _ = await cliente.connect()
        self.assertTrue(conectado, 'el servidor debe aceptar la conexión y esperar "autenticar"')
        self.abiertos.append(cliente)
        return cliente

    async def autenticar(self, cliente, tkn=None):
        await cliente.send_json_to({'tipo': 'autenticar', 'datos': {'token': tkn or token()}})
        return await cliente.receive_json_from(timeout=1)

    async def conectar_autenticado(self, party_id=None):
        cliente = await self.conectar(party_id)
        respuesta = await self.autenticar(cliente)
        self.assertEqual(respuesta['tipo'], 'autenticado')
        return cliente

    async def codigo_de_cierre(self, cliente):
        salida = await cliente.receive_output(timeout=1)
        self.assertEqual(salida['type'], 'websocket.close', f'se esperaba un cierre y llegó {salida}')
        return salida.get('code')

    # --- autenticación (contrato 7.2) ---

    async def test_token_valido_responde_autenticado(self):
        cliente = await self.conectar()
        respuesta = await self.autenticar(cliente)
        self.assertEqual(respuesta['tipo'], 'autenticado')
        self.assertIn('version', respuesta['datos'])

    async def test_sin_autenticar_a_tiempo_cierra_4008(self):
        cliente = await self.conectar()
        self.assertEqual(await self.codigo_de_cierre(cliente), 4008)

    async def test_primer_mensaje_que_no_es_autenticar_cierra_4001(self):
        cliente = await self.conectar()
        await cliente.send_json_to({'tipo': 'latido'})
        self.assertEqual(await self.codigo_de_cierre(cliente), 4001)

    async def test_autenticar_sin_token_cierra_4001(self):
        cliente = await self.conectar()
        await cliente.send_json_to({'tipo': 'autenticar', 'datos': {}})
        self.assertEqual(await self.codigo_de_cierre(cliente), 4001)

    async def test_mensaje_que_no_es_json_cierra_4001(self):
        cliente = await self.conectar()
        await cliente.send_to(text_data='hola')
        self.assertEqual(await self.codigo_de_cierre(cliente), 4001)

    async def test_token_firmado_con_otra_clave_cierra_4001(self):
        cliente = await self.conectar()
        await cliente.send_json_to({'tipo': 'autenticar', 'datos': {'token': token(clave=OTRA_CLAVE_PRIVADA)}})
        self.assertEqual(await self.codigo_de_cierre(cliente), 4001)

    async def test_token_vencido_cierra_4001(self):
        cliente = await self.conectar()
        await cliente.send_json_to({'tipo': 'autenticar', 'datos': {'token': token(vence_en=-10)}})
        self.assertEqual(await self.codigo_de_cierre(cliente), 4001)

    async def test_token_sin_exp_cierra_4001(self):
        # Un token sin 'exp' no vencería nunca.
        cliente = await self.conectar()
        await cliente.send_json_to({'tipo': 'autenticar', 'datos': {'token': token(exp=None)}})
        self.assertEqual(await self.codigo_de_cierre(cliente), 4001)

    async def test_token_sin_sub_cierra_4001(self):
        cliente = await self.conectar()
        await cliente.send_json_to({'tipo': 'autenticar', 'datos': {'token': token(sub=None)}})
        self.assertEqual(await self.codigo_de_cierre(cliente), 4001)

    async def test_token_con_alg_none_cierra_4001(self):
        # Ataque clásico: token sin firma que dice "alg": "none".
        sin_firma = jwt.encode({'sub': str(uuid.uuid4()), 'exp': int(time.time()) + 300}, None, algorithm='none')
        cliente = await self.conectar()
        await cliente.send_json_to({'tipo': 'autenticar', 'datos': {'token': sin_firma}})
        self.assertEqual(await self.codigo_de_cierre(cliente), 4001)

    async def test_reautenticar_con_la_conexion_abierta(self):
        # Contrato 7.2: el cliente renueva el token y manda otro 'autenticar' sin cerrar.
        cliente = await self.conectar_autenticado()
        respuesta = await self.autenticar(cliente, token())
        self.assertEqual(respuesta['tipo'], 'autenticado')

    # --- un grupo por party (criterio de T-30) ---

    async def test_evento_llega_a_los_dos_clientes_de_la_party(self):
        uno = await self.conectar_autenticado()
        dos = await self.conectar_autenticado()

        await publicar(self.party_id, 'miembro.unido', {'usuario_id': 'x'}, version=7)

        for cliente in (uno, dos):
            evento = await cliente.receive_json_from(timeout=1)
            self.assertEqual(evento['tipo'], 'miembro.unido')
            self.assertEqual(evento['datos'], {'usuario_id': 'x'})
            self.assertEqual(evento['version'], 7)

    async def test_evento_usa_el_sobre_comun(self):
        # Contrato 7.3: tipo, evento_id (UUID), enviado_en (ISO 8601 UTC con ms y Z), version, datos.
        cliente = await self.conectar_autenticado()
        await publicar(self.party_id, 'chat.mensaje', {'texto': 'hola'})

        evento = await cliente.receive_json_from(timeout=1)
        self.assertEqual(set(evento), {'tipo', 'evento_id', 'enviado_en', 'version', 'datos'})
        uuid.UUID(evento['evento_id'])
        self.assertRegex(evento['enviado_en'], r'^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}Z$')
        self.assertIsNone(evento['version'])

    async def test_evento_no_llega_a_otra_party(self):
        de_esta = await self.conectar_autenticado()
        de_otra = await self.conectar_autenticado(party_id=uuid.uuid4())

        await publicar(self.party_id, 'miembro.unido', {})

        await de_esta.receive_json_from(timeout=1)
        self.assertTrue(await de_otra.receive_nothing(timeout=0.2))

    async def test_cliente_sin_autenticar_no_recibe_eventos(self):
        autenticado = await self.conectar_autenticado()
        intruso = await self.conectar()

        await publicar(self.party_id, 'chat.mensaje', {'texto': 'privado'})

        await autenticado.receive_json_from(timeout=1)
        salida = await intruso.receive_output(timeout=1)
        # Lo único que puede recibir es el cierre por no autenticarse.
        self.assertEqual(salida['type'], 'websocket.close')
        self.assertEqual(salida.get('code'), 4008)

    async def test_cliente_desconectado_deja_el_grupo(self):
        uno = await self.conectar_autenticado()
        dos = await self.conectar_autenticado()
        await dos.disconnect()
        self.abiertos.remove(dos)

        await publicar(self.party_id, 'miembro.unido', {})  # no debe fallar por el que ya se fue
        await uno.receive_json_from(timeout=1)
