from channels.generic.websocket import AsyncWebsocketConsumer
from django.conf import settings
import json
import jwt
import asyncio

class PartyConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        self.usuario_id = None
        self.sesion_id = None
        self.grupo = None
        await self.accept()
        self.cronometro = asyncio.create_task(self.esperar_autenticacion())

    def autenticado(self):
        return self.usuario_id is not None

    async def esperar_autenticacion(self):
        await asyncio.sleep(settings.WS_TIEMPO_AUTENTICAR)
        if not self.autenticado():
            await self.close(code=4008)

    async def receive(self, text_data=None, bytes_data=None):
        try:
            mensaje = json.loads(text_data)
        except (TypeError, ValueError):
            await self.close(code=4001)
            return

        if mensaje.get('tipo') == 'autenticar':
            await self.autenticar(mensaje)
        elif not self.autenticado():
            await self.close(code=4001)
        # shortcut: other message types from authenticated clients are ignored until the
        # heartbeat ('latido', contract 7.4) is implemented in T-33.

    async def autenticar(self, mensaje):
        datos = mensaje.get('datos') or {}
        token = datos.get('token', '')

        try:
            contenido = jwt.decode(
                token,
                settings.JWT_CLAVE_PUBLICA,
                # Pinning the algorithm rejects 'alg: none' tokens and HS256 tokens signed with the public key.
                algorithms=['RS256'],
                options={'require': ['exp', 'sub']},
            )
        except jwt.InvalidTokenError:
            await self.close(code=4001)
            return

        self.usuario_id = contenido['sub']
        self.sesion_id = contenido.get('sid')

        party_id = self.scope['url_route']['kwargs']['party_id']
        self.grupo = f'party_{party_id}'
        await self.channel_layer.group_add(self.grupo, self.channel_name)

        await self.send(text_data=json.dumps({'tipo': 'autenticado', 'datos': {'version': None}}))

    async def evento(self, mensaje):
        await self.send(text_data=json.dumps(mensaje['mensaje']))

    async def disconnect(self, code):
        self.cronometro.cancel()
        if self.grupo is not None:
            await self.channel_layer.group_discard(self.grupo, self.channel_name)