from unittest import TestCase
from unittest.mock import Mock, patch

from apps.mensajeria.reintentos import esperar_y_reintentar


class EsperarYReintentarTests(TestCase):

    @patch('apps.mensajeria.reintentos.time.sleep')
    @patch('apps.mensajeria.reintentos.connection')
    def test_cierra_rabbitmq_y_la_base_antes_de_reintentar(self, base, dormir):
        conexion = Mock(is_open=True)
        with self.assertLogs('apps.mensajeria.reintentos'):
            esperar_y_reintentar(conexion)
        conexion.close.assert_called_once()
        base.close.assert_called_once()
        dormir.assert_called_once_with(5)

    @patch('apps.mensajeria.reintentos.time.sleep')
    @patch('apps.mensajeria.reintentos.connection')
    def test_sin_conexion_abierta_solo_espera(self, base, dormir):
        with self.assertLogs('apps.mensajeria.reintentos'):
            esperar_y_reintentar(None)
        base.close.assert_called_once()
        dormir.assert_called_once_with(5)
