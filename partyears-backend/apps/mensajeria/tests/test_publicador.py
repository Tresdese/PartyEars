import json
import uuid

import pika
from django.test import TestCase, override_settings

from apps.mensajeria.publicador import publicar_pendientes
from apps.parties.models import EventoSalida
from apps.parties.tests.utilidades import crear_party_en_bd


class CanalFalso:
    """Canal con confirm_delivery: basic_publish falla si el broker no confirma."""

    def __init__(self, rechazar=()):
        self.publicados = []
        self.rechazar = set(rechazar)

    def basic_publish(self, exchange, routing_key, body, properties, mandatory):
        if properties.message_id in self.rechazar:
            raise pika.exceptions.NackError([])
        self.publicados.append((exchange, routing_key, json.loads(body), properties, mandatory))


class PublicarPendientesTests(TestCase):

    def setUp(self):
        self.party_id = crear_party_en_bd(uuid.uuid4())
        self.eventos = [EventoSalida.objects.create(agregado_id=self.party_id, version=v,
                                                    tipo=tipo, datos={'n': v})
                        for v, tipo in ((2, 'miembro.ingreso'), (3, 'party.finalizada'))]

    def publicar(self, canal):
        return publicar_pendientes(canal, EventoSalida, 'party.eventos', 'party')

    def test_publica_en_orden_y_marca_lo_confirmado(self):
        canal = CanalFalso()

        self.assertEqual(self.publicar(canal), 2)

        self.assertEqual([p[1] for p in canal.publicados], ['miembro.ingreso', 'party.finalizada'])
        exchange, _, sobre, propiedades, obligatorio = canal.publicados[0]
        self.assertEqual((exchange, obligatorio, propiedades.delivery_mode),
                         ('party.eventos', True, 2))
        self.assertEqual(propiedades.message_id, str(self.eventos[0].id))
        campos = ('id', 'servicio', 'tipo', 'agregado_id', 'version', 'datos')
        self.assertEqual({k: sobre[k] for k in campos},
                         {'id': str(self.eventos[0].id), 'servicio': 'party',
                          'tipo': 'miembro.ingreso', 'agregado_id': str(self.party_id),
                          'version': 2, 'datos': {'n': 2}})
        self.assertFalse(EventoSalida.objects.filter(publicado_en__isnull=True).exists())

    def test_lo_ya_publicado_no_se_vuelve_a_mandar(self):
        self.publicar(CanalFalso())
        canal = CanalFalso()
        self.assertEqual(self.publicar(canal), 0)
        self.assertEqual(canal.publicados, [])

    def test_si_el_broker_rechaza_uno_se_detiene_para_no_desordenar(self):
        primero, segundo = self.eventos
        with self.assertLogs('apps.mensajeria.publicador', 'WARNING'):
            self.assertEqual(self.publicar(CanalFalso(rechazar={str(primero.id)})), 0)

        primero.refresh_from_db()
        segundo.refresh_from_db()
        self.assertEqual((primero.publicado_en, primero.intentos), (None, 1))
        self.assertIsNone(segundo.publicado_en)
        self.assertEqual(self.publicar(CanalFalso()), 2)
