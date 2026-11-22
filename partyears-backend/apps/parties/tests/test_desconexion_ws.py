import asyncio
import time
import uuid
from unittest import IsolatedAsyncioTestCase

from channels.db import database_sync_to_async
from channels.routing import URLRouter
from channels.testing import WebsocketCommunicator
from django.test import override_settings

from apps.parties.models import ParticipacionParty
from apps.parties.routing import websocket_urlpatterns

from .test_websocket import token
from .utilidades import CLAVE_PUBLICA, agregar_miembro, crear_party_en_bd, vaciar_tablas_party


def participacion(party_id, usuario_id):
    abierta = (ParticipacionParty.objects.filter(party_id=party_id, usuario_id=usuario_id).order_by('-entrada_en').first())
    return abierta.salida_en, abierta.motivo_salida


class DeteccionDesconexionTests(IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        ajustes = override_settings(
            JWT_CLAVE_PUBLICA=CLAVE_PUBLICA,
            WS_TIEMPO_AUTENTICAR=0.3,
            WS_TIEMPO_SIN_LATIDO=0.5,
            CHANNEL_LAYERS={'default': {'BACKEND': 'channels.layers.InMemoryChannelLayer'}},
        )
        ajustes.enable()
        self.addCleanup(ajustes.disable)
        self.anfitrion_id = uuid.uuid4()
        self.party_id = await database_sync_to_async(crear_party_en_bd)(self.anfitrion_id)
        self.abiertos = []
        self.latidos = []

    async def asyncTearDown(self):
        for tarea in self.latidos:
            tarea.cancel()
        await asyncio.gather(*self.latidos, return_exceptions=True)
        for cliente in self.abiertos:
            await cliente.disconnect()
        await database_sync_to_async(vaciar_tablas_party)()

    async def nuevo_miembro(self):
        usuario_id = uuid.uuid4()
        await database_sync_to_async(agregar_miembro)(self.party_id, usuario_id)
        return usuario_id

    async def conectar(self, usuario_id):
        cliente = WebsocketCommunicator(
            URLRouter(websocket_urlpatterns), f'/ws/v1/party/parties/{self.party_id}/')
        conectado, _ = await cliente.connect()
        self.assertTrue(conectado)
        self.abiertos.append(cliente)
        await cliente.send_json_to(
            {'tipo': 'autenticar', 'datos': {'token': token(sub=str(usuario_id))}})
        respuesta = await cliente.receive_json_from(timeout=1)
        self.assertEqual(respuesta['tipo'], 'autenticado')
        return cliente

    async def latir(self, cliente):
        while True:
            await cliente.send_json_to({'tipo': 'latido'})
            await asyncio.sleep(0.15)

    def mantener_vivo(self, cliente):
        self.latidos.append(asyncio.create_task(self.latir(cliente)))

    async def esperar_evento(self, cliente, tipo):
        while True:
            mensaje = await cliente.receive_json_from(timeout=2)
            if mensaje['tipo'] == tipo:
                return mensaje

    async def esperar_cierre(self, cliente):
        while True:
            salida = await cliente.receive_output(timeout=2)
            if salida['type'] == 'websocket.close':
                return salida.get('code')

    async def llega_evento(self, cliente, tipo, ventana):
        limite = time.monotonic() + ventana
        while time.monotonic() < limite:
            if await cliente.receive_nothing(timeout=0.05):
                continue
            mensaje = await cliente.receive_json_from(timeout=1)
            if mensaje['tipo'] == tipo:
                return True
        return False

    async def test_cliente_en_silencio_cierra_4009_y_los_demas_reciben_el_aviso(self):
        host = await self.conectar(self.anfitrion_id)
        self.mantener_vivo(host)
        callado_id = await self.nuevo_miembro()
        callado = await self.conectar(callado_id)

        aviso = await self.esperar_evento(host, 'miembro.desconectado')

        self.assertEqual(aviso['datos'], {'usuario_id': str(callado_id)})
        self.assertEqual(await self.esperar_cierre(callado), 4009)
        salida_en, motivo = await database_sync_to_async(participacion)(
            self.party_id, callado_id)
        self.assertIsNotNone(salida_en)
        self.assertEqual(motivo, 'desconexion')

    async def test_los_latidos_mantienen_la_conexion_y_la_participacion(self):
        cliente = await self.conectar(self.anfitrion_id)
        for _ in range(8):  # 1.2 s: more than twice WS_TIEMPO_SIN_LATIDO
            await cliente.send_json_to({'tipo': 'latido'})
            self.assertEqual(await cliente.receive_json_from(timeout=1), {'tipo': 'latido.ok'})
            await asyncio.sleep(0.15)

        salida_en, _ = await database_sync_to_async(participacion)(
            self.party_id, self.anfitrion_id)
        self.assertIsNone(salida_en)

    async def test_cerrar_el_socket_marca_desconectado_sin_esperar_el_silencio(self):
        host = await self.conectar(self.anfitrion_id)
        self.mantener_vivo(host)
        otro_id = await self.nuevo_miembro()
        otro = await self.conectar(otro_id)

        await otro.disconnect()
        self.abiertos.remove(otro)

        aviso = await self.esperar_evento(host, 'miembro.desconectado')
        self.assertEqual(aviso['datos'], {'usuario_id': str(otro_id)})
        _, motivo = await database_sync_to_async(participacion)(self.party_id, otro_id)
        self.assertEqual(motivo, 'desconexion')

    async def test_si_cae_un_socket_pero_el_usuario_tiene_otro_no_se_marca_desconectado(self):
        host = await self.conectar(self.anfitrion_id)
        self.mantener_vivo(host)
        usuario_id = await self.nuevo_miembro()
        primero = await self.conectar(usuario_id)
        segundo = await self.conectar(usuario_id)
        self.mantener_vivo(segundo)

        await primero.disconnect()
        self.abiertos.remove(primero)

        self.assertFalse(await self.llega_evento(host, 'miembro.desconectado', 0.4))
        salida_en, _ = await database_sync_to_async(participacion)(self.party_id, usuario_id)
        self.assertIsNone(salida_en)