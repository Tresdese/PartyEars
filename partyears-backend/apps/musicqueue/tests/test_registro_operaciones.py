import uuid

from apps.mensajeria.publicador import TIPO_OPERACION
from apps.musicqueue.models import EventoSalida
from .utilidades import PruebasCola


class RegistroOperacionesTests(PruebasCola):
    """RF-34: logs puede seguir una aportación y un rechazo de la cola."""

    def registros(self):
        return [e.datos for e in EventoSalida.objects.filter(tipo=TIPO_OPERACION)]

    def test_una_aportacion_deja_actor_party_y_resultado(self):
        clave = uuid.uuid4()
        self.agregar(self.aportador_id, clave=clave)

        self.assertEqual(self.registros(), [{
            'actor_id': str(self.aportador_id), 'party_id': str(self.party_id),
            'operacion': 'cola.agregar', 'resultado': 201, 'error': None, 'clave': str(clave)}])

    def test_un_rechazo_queda_registrado_sin_cambiar_la_cola(self):
        self.consultar()
        clave = uuid.uuid4()

        self.verificar_error(self.agregar(self.oyente_id, clave=clave), 403, 'SIN_PERMISO')

        self.assertEqual(self.registros(), [{
            'actor_id': str(self.oyente_id), 'party_id': str(self.party_id),
            'operacion': 'cola.agregar', 'resultado': 403, 'error': 'SIN_PERMISO',
            'clave': str(clave)}])
        self.assertFalse(EventoSalida.objects.filter(tipo='cola.actualizada').exists())

    def test_sin_cola_todavia_el_rechazo_no_se_registra_pero_responde_igual(self):
        self.verificar_error(self.agregar(self.oyente_id), 403, 'SIN_PERMISO')
        self.assertEqual(self.registros(), [])
