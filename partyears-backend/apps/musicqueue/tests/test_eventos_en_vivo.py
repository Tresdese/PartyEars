from unittest.mock import patch

from apps.musicqueue.models import EventoSalida
from .utilidades import PruebasCola


class EventosEnVivoTests(PruebasCola):

    def setUp(self):
        super().setUp()
        publicar = patch('apps.musicqueue.servicios.publicar')
        self.publicar = publicar.start()
        self.addCleanup(publicar.stop)

    def publicados(self):
        return [(c.args[1], c.args[3]) for c in self.publicar.call_args_list]

    def test_agregar_avisa_al_grupo_de_la_party_tras_confirmar(self):
        with self.captureOnCommitCallbacks(execute=True):
            estado = self.agregar().json()
        party_id, tipo, datos, version = self.publicar.call_args.args
        self.assertEqual((party_id, tipo, datos, version),
                         (str(self.party_id), 'cola.actualizada', estado, 1))

    def test_el_evento_en_vivo_lleva_el_id_del_outbox(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.agregar()
        self.assertEqual(self.publicar.call_args.kwargs['evento_id'], EventoSalida.objects.get().id)

    def test_iniciar_avisa_reproduccion_y_cola_en_orden(self):
        elemento_id = self.agregar().json()['pendientes'][0]['id']
        self.publicar.reset_mock()
        with self.captureOnCommitCallbacks(execute=True):
            self.reproducir('iniciar')
        self.assertEqual(self.publicados(), [('reproduccion.estado', 2), ('cola.actualizada', 2)])
        self.assertEqual(self.publicar.call_args_list[0].args[2]['elemento_id'], elemento_id)

    def test_pausar_solo_avisa_la_reproduccion(self):
        elemento_id = self.agregar().json()['pendientes'][0]['id']
        self.reproducir('iniciar')
        self.publicar.reset_mock()
        with self.captureOnCommitCallbacks(execute=True):
            self.reproducir('pausar', elemento_id)
        self.assertEqual(self.publicados(), [('reproduccion.estado', 3)])

    def test_operacion_rechazada_no_avisa(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.agregar(self.oyente_id)
        self.publicar.assert_not_called()

    def test_si_redis_falla_el_cambio_sigue_valiendo(self):
        self.publicar.side_effect = ConnectionError
        with self.captureOnCommitCallbacks(execute=True):
            respuesta = self.agregar()
        self.assertEqual(respuesta.status_code, 201)
        self.assertEqual(self.consultar().json()['version'], 1)
