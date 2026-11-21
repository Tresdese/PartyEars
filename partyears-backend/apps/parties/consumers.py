import asyncio
import json
import time
import uuid

import jwt
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.conf import settings

from .servicios import verificar_acceso_websocket


def _es_uuid(texto):
    try:
        uuid.UUID(texto)
    except ValueError:
        return False
    return True


class PartyConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        self.usuario_id = None
        self.sesion_id = None
        self.grupo = None
        await self.accept()
        self.cronometro = asyncio.create_task(self.esperar_autenticacion())

    def esta_autenticado(self):
        return self.usuario_id is not None

    async def esperar_autenticacion(self):
        await asyncio.sleep(settings.WS_TIEMPO_AUTENTICAR)
        if not self.esta_autenticado():
            await self.close(code=4008)

    async def receive(self, text_data=None, bytes_data=None):
        try:
            mensaje = json.loads(text_data)
        except (TypeError, ValueError):
            await self.close(code=4001)
            return
        if not isinstance(mensaje, dict):
            await self.close(code=4001)
            return

        if mensaje.get('tipo') == 'autenticar':
            await self.autenticar(mensaje)
        elif not self.esta_autenticado():
            await self.close(code=4001)
        elif mensaje.get('tipo') == 'reloj.ping':
            await self.responder_reloj(mensaje)
        # TODO(T-38): other message types from authenticated clients are ignored until the
        # heartbeat ('latido', contract 7.4) is implemented.

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
                # Pinning the algorithm rejects 'alg: none' tokens and HS256 tokens
                # signed with the public key.
                algorithms=['RS256'],
                options={'require': ['exp', 'sub']},
            )
        except jwt.InvalidTokenError:
            await self.close(code=4001)
            return

        usuario_id = str(contenido['sub'])
        # Same user instead of any valid token: renewing must not let a connection change owner.
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
        self.sesion_id = contenido.get('sid')
        self.grupo = f'party_{party_id}'
        await self.channel_layer.group_add(self.grupo, self.channel_name)

        await self.send(text_data=json.dumps({'tipo': 'autenticado',
                                              'datos': {'version': version}}))

    async def evento(self, mensaje):
        await self.send(text_data=json.dumps(mensaje['mensaje']))

    async def disconnect(self, code):
        self.cronometro.cancel()
        if self.grupo is not None:
            await self.channel_layer.group_discard(self.grupo, self.channel_name)
