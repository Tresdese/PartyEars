import json
import uuid
from io import StringIO
from types import SimpleNamespace

from unittest.mock import patch

from django.core.management import call_command
from django.db import ProgrammingError
from django.test import TestCase

from apps.logs.management.commands.consumir_eventos import al_recibir
from apps.logs.models import EventoLog
from apps.logs.registro import convertir, guardar


def sobre(servicio='party', tipo='miembro.permisos', datos=None, **extra):
    base = {'id': str(uuid.uuid4()), 'servicio': servicio, 'tipo': tipo,
            'agregado_id': str(uuid.uuid4()), 'version': 7,
            'creado_en': '2026-11-25T10:00:00.123000+00:00',
            'datos': {'usuario_id': str(uuid.uuid4()), 'puede_aportar': False}
            if datos is None else datos}
    return {**base, **extra}


def operacion(servicio, resultado, error=None, party_id=None):
    return sobre(servicio, 'operacion.registrada', {
        'actor_id': str(uuid.uuid4()), 'party_id': str(party_id or uuid.uuid4()),
        'operacion': 'cola.agregar', 'resultado': resultado, 'error': error,
        'clave': str(uuid.uuid4())})


class ConvertirTests(TestCase):

    def test_evento_de_party(self):
        evento = sobre()
        fila = convertir(evento)
        self.assertEqual((fila.servicio_codigo, fila.tipo, fila.nivel, str(fila.party_id),
                          fila.recurso_tipo, str(fila.recurso_id)),
                         ('party', 'miembro.permisos', 'info', evento['agregado_id'], 'party',
                          evento['agregado_id']))
        self.assertEqual(fila.detalle, {**evento['datos'], 'version': 7})
        self.assertEqual(fila.ocurrido_en.isoformat(), '2026-11-25T10:00:00.123000+00:00')

    def test_operacion_de_queue_relaciona_actor_party_y_clave(self):
        evento = operacion('queue', 201)
        fila = convertir(evento)
        datos = evento['datos']
        self.assertEqual((str(fila.actor_usuario_id), str(fila.party_id), str(fila.correlacion_id),
                          fila.recurso_tipo, fila.nivel, fila.mensaje),
                         (datos['actor_id'], datos['party_id'], datos['clave'], 'cola', 'info',
                          'cola.agregar: 201'))

    def test_los_rechazos_son_advertencias_y_las_fallas_errores(self):
        self.assertEqual(convertir(operacion('queue', 403, 'SIN_PERMISO')).nivel, 'warning')
        self.assertEqual(convertir(operacion('queue', 403, 'SIN_PERMISO')).mensaje,
                         'cola.agregar: 403 SIN_PERMISO')
        self.assertEqual(convertir(operacion('queue', 503, 'SERVICIO_NO_DISPONIBLE')).nivel,
                         'error')

    def test_solo_copia_campos_permitidos(self):
        datos = {'usuario_id': 'u', 'codigo': 'ABC123', 'token': 'x', 'texto': 'hola',
                 'nombre_usuario': 'ana', 'miembros': [{'a': 1}]}
        self.assertEqual(convertir(sobre(datos=datos)).detalle, {'usuario_id': 'u', 'version': 7})

    def test_mensajes_invalidos(self):
        for malo in (sobre(servicio='auth'), sobre(datos=[]), {'servicio': 'party'},
                     sobre(id='no-es-uuid')):
            with self.assertRaises((ValueError, KeyError, TypeError)):
                convertir(malo)


class CanalFalso:
    def __init__(self):
        self.confirmados, self.rechazados = [], []

    def basic_ack(self, etiqueta):
        self.confirmados.append(etiqueta)

    def basic_reject(self, etiqueta, requeue):
        self.rechazados.append((etiqueta, requeue))


class ConsumirTests(TestCase):

    def recibir(self, cuerpo, etiqueta=1):
        canal = CanalFalso()
        al_recibir(canal, SimpleNamespace(delivery_tag=etiqueta),
                   SimpleNamespace(message_id='m'), cuerpo)
        return canal

    def test_guarda_y_confirma(self):
        evento = sobre()
        canal = self.recibir(json.dumps(evento).encode())
        self.assertEqual(canal.confirmados, [1])
        self.assertTrue(EventoLog.objects.filter(id=evento['id']).exists())

    def test_un_reenvio_no_duplica(self):
        evento = sobre()
        self.recibir(json.dumps(evento).encode())
        canal = self.recibir(json.dumps(evento).encode(), etiqueta=2)
        self.assertEqual(canal.confirmados, [2])
        self.assertEqual(EventoLog.objects.count(), 1)

    def test_si_falla_la_base_no_confirma_y_la_falla_sube_para_reintentar(self):
        with patch('apps.logs.management.commands.consumir_eventos.guardar',
                   side_effect=ProgrammingError('no existe logs.evento_log')), \
                self.assertRaises(ProgrammingError):
            canal = CanalFalso()
            al_recibir(canal, SimpleNamespace(delivery_tag=1), SimpleNamespace(message_id='m'),
                       json.dumps(sobre()).encode())
        self.assertEqual((canal.confirmados, canal.rechazados), ([], []))

    def test_un_mensaje_invalido_se_descarta_sin_reencolar(self):
        with self.assertLogs('apps.logs.management.commands.consumir_eventos'):
            canal = self.recibir(b'{no es json')
        self.assertEqual((canal.confirmados, canal.rechazados), ([], [(1, False)]))


class VerRegistrosTests(TestCase):

    def ver(self, **filtros):
        salida = StringIO()
        call_command('ver_registros', stdout=salida, **filtros)
        return salida.getvalue()

    def test_sigue_una_operacion_por_party(self):
        party_id = uuid.uuid4()
        guardar(operacion('queue', 403, 'SIN_PERMISO', party_id=party_id))
        guardar(operacion('queue', 201))

        salida = self.ver(party=str(party_id))

        self.assertIn('cola.agregar: 403 SIN_PERMISO', salida)
        self.assertEqual(len(salida.strip().splitlines()), 1)

    def test_sin_resultados_lo_dice(self):
        self.assertIn('No hay registros', self.ver(party=str(uuid.uuid4())))
