import time
import uuid
from unittest import IsolatedAsyncioTestCase

import jwt
from channels.db import database_sync_to_async
from channels.routing import URLRouter
from channels.testing import WebsocketCommunicator
from django.test import override_settings
from django.utils import timezone

from apps.parties.eventos import publicar
from apps.parties.models import MiembroParty, ParticipacionParty, Party
from apps.parties.routing import websocket_urlpatterns

from .utilidades import (CLAVE_PRIVADA, CLAVE_PUBLICA, OTRA_CLAVE_PRIVADA, agregar_miembro,
                         crear_party_en_bd, vaciar_tablas_party)


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
    datos = {k: v for k, v in datos.items() if v is not None}
    return jwt.encode(datos, clave, algorithm='RS256')

# Not SimpleTestCase: Django never calls asyncTearDown, so connections would leak between tests.
class WebSocketPartyTests(IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        ajustes = override_settings(
            JWT_CLAVE_PUBLICA=CLAVE_PUBLICA,
            WS_TIEMPO_AUTENTICAR=0.3,
            CHANNEL_LAYERS={'default': {'BACKEND': 'channels.layers.InMemoryChannelLayer'}},
        )
        ajustes.enable()
        self.addCleanup(ajustes.disable)
        self.anfitrion_id = uuid.uuid4()
        self.party_id = await database_sync_to_async(crear_party_en_bd)(self.anfitrion_id)
        self.abiertos = []

    async def asyncTearDown(self):
        for cliente in self.abiertos:
            await cliente.disconnect()
        await database_sync_to_async(vaciar_tablas_party)()

    async def conectar(self, party_id=None):
        cliente = WebsocketCommunicator(
            URLRouter(websocket_urlpatterns), f'/ws/v1/party/parties/{party_id or self.party_id}/'
        )
        conectado, _ = await cliente.connect()
        self.assertTrue(conectado, 'el servidor debe aceptar la conexión y esperar "autenticar"')
        self.abiertos.append(cliente)
        return cliente

    async def autenticar(self, cliente, tkn=None):
        await self.autenticar_sin_respuesta(cliente, tkn)
        return await cliente.receive_json_from(timeout=1)

    async def autenticar_sin_respuesta(self, cliente, tkn=None):
        await cliente.send_json_to({'tipo': 'autenticar', 'datos': {'token': tkn or token()}})

    async def agregar_miembro(self, party_id=None, esta_conectado=True):
        usuario_id = uuid.uuid4()
        await database_sync_to_async(agregar_miembro)(party_id or self.party_id, usuario_id,
                                                      esta_conectado)
        return usuario_id

    async def conectar_autenticado(self, party_id=None):
        usuario_id = await self.agregar_miembro(party_id)
        cliente = await self.conectar(party_id)
        respuesta = await self.autenticar(cliente, token(sub=str(usuario_id)))
        self.assertEqual(respuesta['tipo'], 'autenticado')
        return cliente

    async def codigo_de_cierre(self, cliente):
        salida = await cliente.receive_output(timeout=1)
        self.assertEqual(salida['type'], 'websocket.close',
                         f'se esperaba un cierre y llegó {salida}')
        return salida.get('code')

    async def test_miembro_conectado_recibe_autenticado_con_la_version(self):
        cliente = await self.conectar()
        respuesta = await self.autenticar(cliente, token(sub=str(self.anfitrion_id)))
        self.assertEqual(respuesta, {'tipo': 'autenticado', 'datos': {'version': 1}})

    async def test_quien_no_es_miembro_cierra_4003(self):
        cliente = await self.conectar()
        await self.autenticar_sin_respuesta(cliente, token())
        self.assertEqual(await self.codigo_de_cierre(cliente), 4003)

    async def test_miembro_que_ya_salio_cierra_4003(self):
        usuario_id = await self.agregar_miembro(esta_conectado=False)
        cliente = await self.conectar()
        await self.autenticar_sin_respuesta(cliente, token(sub=str(usuario_id)))
        self.assertEqual(await self.codigo_de_cierre(cliente), 4003)

    async def test_expulsado_cierra_4003(self):
        usuario_id = await self.agregar_miembro()
        await database_sync_to_async(
            MiembroParty.objects.filter(usuario_id=usuario_id).update)(estado='expulsado')
        cliente = await self.conectar()
        await self.autenticar_sin_respuesta(cliente, token(sub=str(usuario_id)))
        self.assertEqual(await self.codigo_de_cierre(cliente), 4003)

    async def test_party_que_no_existe_cierra_4004(self):
        cliente = await self.conectar(party_id=uuid.uuid4())
        await self.autenticar_sin_respuesta(cliente, token(sub=str(self.anfitrion_id)))
        self.assertEqual(await self.codigo_de_cierre(cliente), 4004)

    async def test_party_finalizada_cierra_4010(self):
        await database_sync_to_async(
            Party.objects.filter(id=self.party_id).update)(finalizada_en=timezone.now())
        cliente = await self.conectar()
        await self.autenticar_sin_respuesta(cliente, token(sub=str(self.anfitrion_id)))
        self.assertEqual(await self.codigo_de_cierre(cliente), 4010)

    async def test_token_con_sub_que_no_es_uuid_cierra_4001(self):
        cliente = await self.conectar()
        await self.autenticar_sin_respuesta(cliente, token(sub='axel'))
        self.assertEqual(await self.codigo_de_cierre(cliente), 4001)

    async def test_mensaje_json_que_no_es_objeto_cierra_4001(self):
        for texto in ('[]', '"autenticar"', '7'):
            cliente = await self.conectar()
            await cliente.send_to(text_data=texto)
            self.assertEqual(await self.codigo_de_cierre(cliente), 4001, texto)

    async def test_datos_de_autenticar_que_no_son_objeto_cierra_4001(self):
        cliente = await self.conectar()
        await cliente.send_json_to({'tipo': 'autenticar', 'datos': 'token'})
        self.assertEqual(await self.codigo_de_cierre(cliente), 4001)

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
        await self.autenticar_sin_respuesta(cliente, token(clave=OTRA_CLAVE_PRIVADA))
        self.assertEqual(await self.codigo_de_cierre(cliente), 4001)

    async def test_token_vencido_cierra_4001(self):
        cliente = await self.conectar()
        await cliente.send_json_to({'tipo': 'autenticar', 'datos': {'token': token(vence_en=-10)}})
        self.assertEqual(await self.codigo_de_cierre(cliente), 4001)

    async def test_token_sin_exp_cierra_4001(self):
        cliente = await self.conectar()
        await cliente.send_json_to({'tipo': 'autenticar', 'datos': {'token': token(exp=None)}})
        self.assertEqual(await self.codigo_de_cierre(cliente), 4001)

    async def test_token_sin_sub_cierra_4001(self):
        cliente = await self.conectar()
        await cliente.send_json_to({'tipo': 'autenticar', 'datos': {'token': token(sub=None)}})
        self.assertEqual(await self.codigo_de_cierre(cliente), 4001)

    async def test_token_con_alg_none_cierra_4001(self):
        datos = {'sub': str(uuid.uuid4()), 'exp': int(time.time()) + 300}
        sin_firma = jwt.encode(datos, None, algorithm='none')
        cliente = await self.conectar()
        await cliente.send_json_to({'tipo': 'autenticar', 'datos': {'token': sin_firma}})
        self.assertEqual(await self.codigo_de_cierre(cliente), 4001)

    async def test_reautenticar_con_la_conexion_abierta(self):
        cliente = await self.conectar()
        await self.autenticar(cliente, token(sub=str(self.anfitrion_id)))
        respuesta = await self.autenticar(cliente, token(sub=str(self.anfitrion_id)))
        self.assertEqual(respuesta['tipo'], 'autenticado')

    async def test_token_que_vence_con_la_conexion_abierta_cierra_4001(self):
        cliente = await self.conectar()
        await self.autenticar(cliente, token(sub=str(self.anfitrion_id), vence_en=1))
        salida = await cliente.receive_output(timeout=2.5)
        self.assertEqual((salida['type'], salida.get('code')), ('websocket.close', 4001))

    async def test_renovar_el_token_antes_de_que_venza_mantiene_la_conexion(self):
        cliente = await self.conectar()
        # 2 s instead of 1: exp is whole seconds, so 1 s can run out before the renewal arrives.
        await self.autenticar(cliente, token(sub=str(self.anfitrion_id), vence_en=2))
        await self.autenticar(cliente, token(sub=str(self.anfitrion_id)))
        self.assertTrue(await cliente.receive_nothing(timeout=3))

    async def test_reautenticar_con_otro_usuario_cierra_4001(self):
        otro_id = await self.agregar_miembro()
        cliente = await self.conectar()
        await self.autenticar(cliente, token(sub=str(self.anfitrion_id)))
        await self.autenticar_sin_respuesta(cliente, token(sub=str(otro_id)))
        self.assertEqual(await self.codigo_de_cierre(cliente), 4001)

    async def test_reautenticar_tras_salir_de_la_party_cierra_4003(self):
        cliente = await self.conectar()
        await self.autenticar(cliente, token(sub=str(self.anfitrion_id)))
        await database_sync_to_async(
            ParticipacionParty.objects.filter(usuario_id=self.anfitrion_id).update)(
            salida_en=timezone.now(), motivo_salida='voluntaria')
        await self.autenticar_sin_respuesta(cliente, token(sub=str(self.anfitrion_id)))
        self.assertEqual(await self.codigo_de_cierre(cliente), 4003)

    async def test_autenticado_que_manda_otro_mensaje_no_es_expulsado(self):
        cliente = await self.conectar_autenticado()
        await cliente.send_json_to({'tipo': 'latido'})
        await publicar(self.party_id, 'miembro.unido', {})
        evento = await cliente.receive_json_from(timeout=1)
        self.assertEqual(evento['tipo'], 'miembro.unido')

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
        cliente = await self.conectar_autenticado()
        await publicar(self.party_id, 'chat.mensaje', {'texto': 'hola'})

        evento = await cliente.receive_json_from(timeout=1)
        self.assertEqual(set(evento), {'tipo', 'evento_id', 'enviado_en', 'version', 'datos'})
        uuid.UUID(evento['evento_id'])
        self.assertRegex(evento['enviado_en'], r'^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}Z$')
        self.assertIsNone(evento['version'])

    async def test_evento_no_llega_a_otra_party(self):
        otra_party_id = await database_sync_to_async(crear_party_en_bd)(uuid.uuid4())
        de_esta = await self.conectar_autenticado()
        de_otra = await self.conectar_autenticado(party_id=otra_party_id)

        await publicar(self.party_id, 'miembro.unido', {})

        await de_esta.receive_json_from(timeout=1)
        self.assertTrue(await de_otra.receive_nothing(timeout=0.2))

    async def test_cliente_sin_autenticar_no_recibe_eventos(self):
        autenticado = await self.conectar_autenticado()
        intruso = await self.conectar()

        await publicar(self.party_id, 'chat.mensaje', {'texto': 'privado'})

        await autenticado.receive_json_from(timeout=1)
        salida = await intruso.receive_output(timeout=1)

        self.assertEqual(salida['type'], 'websocket.close')
        self.assertEqual(salida.get('code'), 4008)

    async def test_cliente_desconectado_deja_el_grupo(self):
        uno = await self.conectar_autenticado()
        dos = await self.conectar_autenticado()
        await dos.disconnect()
        self.abiertos.remove(dos)

        await publicar(self.party_id, 'miembro.unido', {})
        await uno.receive_json_from(timeout=1)

    async def test_reloj_ping_responde_con_la_hora_del_servidor(self):
        cliente = await self.conectar_autenticado()
        antes = time.time_ns() // 1_000_000

        await cliente.send_json_to({'tipo': 'reloj.ping', 'datos': {'t_cliente': 123}})
        respuesta = await cliente.receive_json_from(timeout=1)

        self.assertEqual(respuesta['tipo'], 'reloj.pong')
        self.assertEqual(respuesta['datos']['t_cliente'], 123)
        self.assertGreaterEqual(respuesta['datos']['t_servidor'], antes)
        self.assertLessEqual(respuesta['datos']['t_servidor'], time.time_ns() // 1_000_000)

    async def test_reloj_ping_sin_autenticar_cierra_4001(self):
        cliente = await self.conectar()
        await cliente.send_json_to({'tipo': 'reloj.ping', 'datos': {'t_cliente': 123}})
        salida = await cliente.receive_output(timeout=1)
        self.assertEqual(salida.get('code'), 4001)

    async def test_reloj_ping_con_datos_invalidos_no_rompe_la_conexion(self):
        cliente = await self.conectar_autenticado()
        await cliente.send_json_to({'tipo': 'reloj.ping', 'datos': 'basura'})
        respuesta = await cliente.receive_json_from(timeout=1)
        self.assertIsNone(respuesta['datos']['t_cliente'])
