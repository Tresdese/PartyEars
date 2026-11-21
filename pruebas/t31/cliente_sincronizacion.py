"""Cliente de prueba de T-31: reproduce un audio con mpv siguiendo reproduccion.estado (contrato 5.3).

Solo necesita Python 3.10+, mpv y `pip install websockets`. Ver README.md.
"""
import argparse
import asyncio
import csv
import itertools
import json
import os
import statistics
import tempfile
import time
from datetime import datetime

import websockets


def ahora_ms():
    return time.time_ns() // 1_000_000


def iso_a_ms(texto):
    return int(datetime.fromisoformat(texto.replace('Z', '+00:00')).timestamp() * 1000)


def posicion_esperada(estado, hora_servidor):
    """Fórmula del contrato 5.3."""
    if estado['estado'] == 'reproduciendo':
        return estado['posicion_base_ms'] + (hora_servidor - iso_a_ms(estado['referencia_en']))
    return estado['posicion_base_ms']


def desfase_de_reloj(t_cliente, t_servidor, t_recibido):
    """Contrato 7.4: supone que la ida y la vuelta tardan lo mismo."""
    return t_servidor - (t_cliente + t_recibido) / 2


class Mpv:
    """Control mínimo de mpv por su socket JSON (--input-ipc-server)."""

    def __init__(self, audio, extra):
        self.audio = audio
        self.extra = extra
        self.socket = os.path.join(tempfile.gettempdir(), f'mpv-t31-{os.getpid()}.sock')
        self.ids = itertools.count(1)
        self.pendientes = {}

    async def iniciar(self):
        self.proceso = await asyncio.create_subprocess_exec(
            'mpv', '--no-video', '--idle=yes', '--pause', '--keep-open=yes', '--really-quiet',
            f'--input-ipc-server={self.socket}', *self.extra, self.audio,
        )
        for _ in range(50):
            try:
                self.lector, self.escritor = await asyncio.open_unix_connection(self.socket)
                break
            except (FileNotFoundError, ConnectionRefusedError):
                await asyncio.sleep(0.1)
        else:
            raise RuntimeError('mpv no abrió su socket')
        asyncio.create_task(self._leer())
        while await self.posicion_ms() is None:
            await asyncio.sleep(0.05)

    async def _leer(self):
        async for linea in self.lector:
            respuesta = json.loads(linea)
            futuro = self.pendientes.pop(respuesta.get('request_id'), None)
            if futuro is not None:
                futuro.set_result(respuesta)

    async def comando(self, *args):
        request_id = next(self.ids)
        futuro = asyncio.get_running_loop().create_future()
        self.pendientes[request_id] = futuro
        self.escritor.write(json.dumps({'command': list(args), 'request_id': request_id}).encode() + b'\n')
        await self.escritor.drain()
        return await futuro

    async def posicion_ms(self):
        respuesta = await self.comando('get_property', 'time-pos')
        valor = respuesta.get('data')
        return None if valor is None else valor * 1000

    async def ir_a(self, posicion_ms):
        await self.comando('seek', max(posicion_ms, 0) / 1000, 'absolute+exact')

    async def pausar(self, pausado):
        await self.comando('set_property', 'pause', pausado)

    async def velocidad(self, valor):
        await self.comando('set_property', 'speed', valor)

    def cerrar(self):
        if self.proceso.returncode is None:
            self.proceso.terminate()


class Cliente:
    def __init__(self, args):
        self.args = args
        self.mpv = Mpv(args.audio, args.mpv_arg)
        self.estado = None
        self.desfase = 0
        self.rtt = None
        self.pong = None
        self.arranque = None
        self.errores = []
        self.correcciones = 0

    def hora_servidor(self):
        return ahora_ms() + self.desfase

    async def medir_reloj(self, ws, veces):
        """Contrato 7.4: se queda con la medición de menor ida y vuelta."""
        mejor = None
        for _ in range(veces):
            self.pong = asyncio.get_running_loop().create_future()
            t_cliente = ahora_ms()
            await ws.send(json.dumps({'tipo': 'reloj.ping', 'datos': {'t_cliente': t_cliente}}))
            datos = await asyncio.wait_for(self.pong, timeout=2)
            t_recibido = ahora_ms()
            rtt = t_recibido - t_cliente
            if mejor is None or rtt < mejor[0]:
                mejor = (rtt, desfase_de_reloj(t_cliente, datos['t_servidor'], t_recibido))
            await asyncio.sleep(0.05)
        self.rtt, self.desfase = mejor

    async def recibir(self, ws):
        async for texto in ws:
            mensaje = json.loads(texto)
            if mensaje['tipo'] == 'reloj.pong' and self.pong and not self.pong.done():
                self.pong.set_result(mensaje['datos'])
            elif mensaje['tipo'] == 'reproduccion.estado':
                await self.aplicar(mensaje['datos'])

    async def aplicar(self, estado):
        self.estado = estado
        if self.arranque:
            self.arranque.cancel()
        await self.mpv.velocidad(1.0)
        if estado['estado'] != 'reproduciendo':
            await self.mpv.pausar(True)
            await self.mpv.ir_a(estado['posicion_base_ms'])
            print(f'{self.args.nombre}: {estado["estado"]} en {estado["posicion_base_ms"]} ms', flush=True)
            return

        # The controller sets referencia_en slightly in the future so every client
        # pre-seeks and starts at the same instant instead of when the message arrives.
        espera_ms = iso_a_ms(estado['referencia_en']) - self.hora_servidor()
        if espera_ms > 0:
            await self.mpv.pausar(True)
            await self.mpv.ir_a(estado['posicion_base_ms'])
            self.arranque = asyncio.create_task(self.arrancar_en(espera_ms / 1000))
        else:
            await self.mpv.ir_a(posicion_esperada(estado, self.hora_servidor()))
            await self.mpv.pausar(False)
        print(f'{self.args.nombre}: reproduciendo desde {estado["posicion_base_ms"]} ms '
              f'(arranca en {max(espera_ms, 0):.0f} ms)', flush=True)

    async def arrancar_en(self, segundos):
        await asyncio.sleep(segundos)
        await self.mpv.pausar(False)

    async def corregir(self, salida):
        while True:
            await asyncio.sleep(self.args.cada_ms / 1000)
            if not self.estado or self.estado['estado'] != 'reproduciendo':
                continue
            # Before referencia_en the client is pre-seeked and paused on purpose.
            if self.arranque is not None and not self.arranque.done():
                continue
            esperada = posicion_esperada(self.estado, self.hora_servidor())
            real = await self.mpv.posicion_ms()
            if real is None:
                continue
            # The IPC round trip happens between both readings; take the expected
            # position again so the error does not include it.
            esperada = (esperada + posicion_esperada(self.estado, self.hora_servidor())) / 2
            error = real - esperada
            accion = ''
            if abs(error) > self.args.limite_ms:
                accion = await self.correccion(esperada, error)
            elif self.args.metodo == 'velocidad' and abs(error) < self.args.limite_ms / 2:
                await self.mpv.velocidad(1.0)
            self.errores.append(error)
            salida.writerow([self.hora_servidor(), self.estado['estado'], round(esperada),
                             round(real), round(error), accion, self.rtt, round(self.desfase)])

    async def correccion(self, esperada, error):
        self.correcciones += 1
        if self.args.metodo == 'saltar':
            await self.mpv.ir_a(esperada)
            return 'saltar'
        # Proportional: recover the error over ~2 s, never more than ±5 % (audible above that).
        velocidad = min(max(1 - error / 2000, 0.95), 1.05)
        await self.mpv.velocidad(velocidad)
        return f'velocidad {velocidad:.3f}'

    async def remedir_reloj(self, ws):
        while True:
            await asyncio.sleep(30)
            await self.medir_reloj(ws, 5)

    async def ejecutar(self):
        await self.mpv.iniciar()
        async with websockets.connect(self.args.url) as ws:
            await ws.send(json.dumps({'tipo': 'autenticar', 'datos': {'token': self.args.token}}))
            respuesta = json.loads(await ws.recv())
            if respuesta.get('tipo') != 'autenticado':
                raise RuntimeError(f'autenticación rechazada: {respuesta}')
            receptor = asyncio.create_task(self.recibir(ws))
            await self.medir_reloj(ws, 15)
            print(f'{self.args.nombre}: listo. Desfase de reloj {self.desfase:+.0f} ms, '
                  f'ida y vuelta {self.rtt} ms', flush=True)
            with open(self.args.csv, 'w', newline='') as archivo:
                salida = csv.writer(archivo)
                salida.writerow(['t_servidor_ms', 'estado', 'esperada_ms', 'real_ms', 'error_ms',
                                 'accion', 'rtt_ms', 'desfase_reloj_ms'])
                await asyncio.gather(receptor, self.corregir(salida), self.remedir_reloj(ws))

    def resumen(self):
        if not self.errores:
            print('sin mediciones')
            return
        absolutos = sorted(abs(e) for e in self.errores)
        p95 = absolutos[int(len(absolutos) * 0.95) - 1] if len(absolutos) >= 20 else absolutos[-1]
        print(f'\n{self.args.nombre}: {len(absolutos)} mediciones, error medio '
              f'{statistics.mean(self.errores):+.0f} ms, |error| p95 {p95:.0f} ms, '
              f'máximo {absolutos[-1]:.0f} ms, correcciones {self.correcciones}. CSV: {self.args.csv}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', required=True, help='ws://<ip>:8003/ws/v1/party/parties/<party_id>/')
    parser.add_argument('--token', required=True, help='token de controlar.py token')
    parser.add_argument('--audio', required=True)
    parser.add_argument('--nombre', default=os.uname().nodename)
    parser.add_argument('--metodo', choices=['saltar', 'velocidad'], default='saltar')
    parser.add_argument('--limite-ms', type=float, default=100)
    parser.add_argument('--cada-ms', type=float, default=500, help='cada cuánto se mide el error')
    parser.add_argument('--csv', default='sincronizacion.csv')
    parser.add_argument('--mpv-arg', action='append', default=[], help='argumento extra para mpv')
    cliente = Cliente(parser.parse_args())
    try:
        asyncio.run(cliente.ejecutar())
    except KeyboardInterrupt:
        pass
    except websockets.ConnectionClosed as cierre:
        print(f'{cliente.args.nombre}: el servidor cerró la conexión ({cierre})')
    finally:
        cliente.mpv.cerrar()
        cliente.resumen()


if __name__ == '__main__':
    main()
