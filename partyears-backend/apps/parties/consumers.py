import asyncio
import json
import logging
import time
import uuid

import jwt
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.conf import settings

from .servicios import CIERRE_SIN_LATIDO, desconectar_participante, verificar_acceso_websocket

logger = logging.getLogger(__name__)

_conexiones = {}


def _es_uuid(texto):
    try:
        uuid.UUID(texto)
    except ValueError:
        return False
    return True


class PartyConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        self.usuario_id = None
        self.party_id = None
        self.sesion_id = None
        self.grupo = None
        self.vencimiento = None
        self.silencio = None
        self.detectado = False
        await self.accept()
        self.cronometro = asyncio.create_task(self.esperar_autenticacion())

    def esta_autenticado(self):
        return self.usuario_id is not None

    async def esperar_autenticacion(self):
        await asyncio.sleep(settings.WS_TIEMPO_AUTENTICAR)
        if not self.esta_autenticado():
            await self.close(code=4008)

    async def cerrar_al_vencer(self, exp):
        await asyncio.sleep(max(exp - time.time(), 0))
        await self.close(code=4001)

    def reiniciar_silencio(self):
        if self.detectado:
            return
        if self.silencio is not None:
            self.silencio.cancel()
        self.silencio = asyncio.create_task(self.vigilar_silencio())

    async def vigilar_silencio(self):
        await asyncio.sleep(settings.WS_TIEMPO_SIN_LATIDO)
        self.detectado = True
        await self.marcar_desconectado()
        await self.close(code=CIERRE_SIN_LATIDO)

    async def marcar_desconectado(self):
        if not self.esta_autenticado() or self.party_id is None:
            return
        clave = (self.party_id, self.usuario_id)
        sockets = _conexiones.get(clave, set())
        sockets.discard(self)
        if sockets:
            return
        _conexiones.pop(clave, None)
        try:
            await database_sync_to_async(desconectar_participante)(self.party_id, self.usuario_id)
        except Exception:
            logger.exception('No se pudo registrar la desconexión de %s en la party %s', self.usuario_id, self.party_id)

    async def receive(self, text_data=None, bytes_data=None):
        if self.detectado:
            return
        try:
            mensaje = json.loads(text_data)
        except (TypeError, ValueError):
            await self.close(code=4001)
            return
        if not isinstance(mensaje, dict):
            await self.close(code=4001)
            return

        if self.esta_autenticado():
            self.reiniciar_silencio()

        if mensaje.get('tipo') == 'autenticar':
            self.cronometro.cancel()
            await self.autenticar(mensaje)
        elif not self.esta_autenticado():
            await self.close(code=4001)
        elif mensaje.get('tipo') == 'reloj.ping':
            await self.responder_reloj(mensaje)
        elif mensaje.get('tipo') == 'latido':
            await self.send(text_data=json.dumps({'tipo': 'latido.ok'}))

    async def responder_reloj(self, mensaje):
        datos = mensaje.get('datos')
        t_cliente = datos.get('t_cliente') if isinstance(datos, dict) else None
        await self.send(text_data=json.dumps({
            'tipo': 'reloj.pong',
            'datos': {'t_cliente': t_cliente, 't_servidor': time.time_ns() // 1_000_000},
        }))

    async def autenticar(self, mensaje):
        datos = mensaje.get('datos')
        token = datos.get('token', '') if isinstance(datos, dict) else ''

        try:
            contenido = jwt.decode(
                token,
                settings.JWT_CLAVE_PUBLICA,
                algorithms=['RS256'],
                options={'require': ['exp', 'sub']},
            )
        except jwt.InvalidTokenError:
            await self.close(code=4001)
            return

        usuario_id = str(contenido['sub'])
        es_otro_usuario = self.esta_autenticado() and usuario_id != self.usuario_id
        if not _es_uuid(usuario_id) or es_otro_usuario:
            await self.close(code=4001)
            return

        party_id = self.scope['url_route']['kwargs']['party_id']
        # TODO(T-40): membership is checked only here; an expelled member keeps the socket
        # until expulsion closes it explicitly.
        cierre, version = await database_sync_to_async(verificar_acceso_websocket)(party_id,
                                                                                   usuario_id)
        if cierre is not None:
            await self.close(code=cierre)
            return

        self.usuario_id = usuario_id
        self.party_id = str(party_id)
        self.sesion_id = contenido.get('sid')
        self.grupo = f'party_{party_id}'
        _conexiones.setdefault((self.party_id, self.usuario_id), set()).add(self)
        if self.vencimiento is not None:
            self.vencimiento.cancel()
        self.vencimiento = asyncio.create_task(self.cerrar_al_vencer(contenido['exp']))
        await self.channel_layer.group_add(self.grupo, self.channel_name)
        self.reiniciar_silencio()

        await self.send(text_data=json.dumps({'tipo': 'autenticado', 'datos': {'version': version}}))

    async def evento(self, mensaje):
        await self.send(text_data=json.dumps(mensaje['mensaje']))

    async def disconnect(self, code):
        self.cronometro.cancel()
        if self.vencimiento is not None:
            self.vencimiento.cancel()
        if self.silencio is not None:
            self.silencio.cancel()
        if self.grupo is not None:
            await self.channel_layer.group_discard(self.grupo, self.channel_name)
        await self.marcar_desconectado()