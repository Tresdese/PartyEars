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

# shortcut: per-process registry, wrong with more than one Daphne worker; move it to Redis
# if party ever runs on several processes.
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
        self.cerrado = False
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
        if not self.cerrado:
            await self.close(code=CIERRE_SIN_LATIDO)

    async def marcar_desconectado(self):
        if not self.esta_autenticado() or self.party_id is None:
            return
        self.olvidar_socket()
        if _conexiones.get((self.party_id, self.usuario_id)):
            return
        try:
            await database_sync_to_async(desconectar_participante)(self.party_id, self.usuario_id)
        except Exception:
            logger.exception('No se pudo registrar la desconexión de %s en la party %s',
                             self.usuario_id, self.party_id)

    def olvidar_socket(self):
        clave = (self.party_id, self.usuario_id)
        sockets = _conexiones.get(clave, set())
        sockets.discard(self)
        if not sockets:
            _conexiones.pop(clave, None)

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
            # The deadline covers sending autenticar, not the membership query: every path of
            # autenticar ends authenticated or closed.
            self.cronometro.cancel()
            await self.autenticar(mensaje)
        elif not self.esta_autenticado():
            await self.close(code=4001)
        elif mensaje.get('tipo') == 'reloj.ping':
            await self.responder_reloj(mensaje)
        elif mensaje.get('tipo') == 'latido':
            # Answering instead of ignoring: the client drops the socket after 15 s without
            # hearing from the server, so a quiet party would reconnect every 15 s.
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
        # Timer instead of checking exp on each message: the server pushes events to idle clients.
        if self.vencimiento is not None:
            self.vencimiento.cancel()
        self.vencimiento = asyncio.create_task(self.cerrar_al_vencer(contenido['exp']))
        await self.channel_layer.group_add(self.grupo, self.channel_name)
        self.reiniciar_silencio()

        await self.send(text_data=json.dumps({'tipo': 'autenticado',
                                              'datos': {'version': version}}))

    async def evento(self, mensaje):
        evento = mensaje['mensaje']
        await self.send(text_data=json.dumps(evento))
        cierre = self.cierre_tras(evento)
        if cierre is not None:
            await self.close(code=cierre)

    def cierre_tras(self, evento):
        # Closing here instead of trusting the client: whoever left or whose party ended must
        # stop receiving updates (RF-19, RF-20, RF-30), even if the app never closes the socket.
        if evento['tipo'] == 'party.finalizada':
            return 4010
        if evento['tipo'] in ('miembro.salida', 'miembro.expulsado'):
            saliente = str(evento['datos'].get('usuario_id', '')).lower()
            if self.usuario_id is not None and saliente == self.usuario_id.lower():
                return 4003
        return None

    async def disconnect(self, code):
        self.cerrado = True
        self.cronometro.cancel()
        if self.vencimiento is not None:
            self.vencimiento.cancel()
        if self.grupo is not None:
            await self.channel_layer.group_discard(self.grupo, self.channel_name)
        # Leaving the silence timer running instead of marking now: a closed socket is not yet
        # a disconnection (SRS: 15 s without valid messages). Renewing the token (4001), a
        # network blip or the client's own reconnect opens a new socket within that window,
        # and closing the participation here would answer it with 4003.
        if self.esta_autenticado():
            self.olvidar_socket()
