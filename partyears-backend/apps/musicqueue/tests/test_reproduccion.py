import threading
import uuid
from datetime import timedelta
from unittest.mock import patch

from django.db import connection
from django.utils import timezone

from apps.musicqueue.models import ElementoCola, EventoSalida
from apps.musicqueue.servicios import ADELANTO_ARRANQUE
from .utilidades import PruebasCola, PruebasColaConcurrentes


class PruebasReproduccion(PruebasCola):

    def setUp(self):
        super().setUp()
        for _ in range(3):
            estado = self.agregar().json()
        self.a, self.b, self.c = self.ids_pendientes(estado)

    def iniciar(self):
        return self.reproducir('iniciar').json()

    def estado_de(self, elemento_id):
        return ElementoCola.objects.get(id=elemento_id).estado

    def adelantar_reloj(self, segundos):
        """Corre el reloj del servidor para simular tiempo de reproducción."""
        futuro = timezone.now() + timedelta(seconds=segundos)
        reloj = patch('apps.musicqueue.servicios.timezone.now', return_value=futuro)
        reloj.start()
        self.addCleanup(reloj.stop)


class IniciarTests(PruebasReproduccion):

    def test_empieza_la_primera_pendiente_desde_cero_con_adelanto(self):
        antes = timezone.now()
        estado = self.iniciar()
        self.assertEqual((estado['estado'], estado['elemento_id'], estado['posicion_base_ms']),
                         ('reproduciendo', self.a, 0))
        referencia = ElementoCola.objects.get(id=self.a).referencia_en
        self.assertGreaterEqual(referencia, antes + ADELANTO_ARRANQUE)

    def test_la_cola_muestra_el_actual_con_su_reproduccion(self):
        self.iniciar()
        cola = self.consultar().json()
        self.assertEqual(cola['actual']['elemento']['id'], self.a)
        self.assertEqual(cola['actual']['reproduccion']['estado'], 'reproduciendo')
        self.assertEqual(self.ids_pendientes(cola), [self.b, self.c])

    def test_con_algo_sonando_es_reproduccion_en_curso(self):
        self.iniciar()
        self.verificar_error(self.reproducir('iniciar'), 409, 'REPRODUCCION_EN_CURSO')

    def test_cola_vacia(self):
        for elemento_id in (self.a, self.b, self.c):
            self.retirar(elemento_id, self.consultar().json()['version'])
        self.verificar_error(self.reproducir('iniciar'), 409, 'COLA_VACIA')

    def test_solo_el_anfitrion(self):
        self.verificar_error(self.reproducir('iniciar', usuario_id=self.modificador_id), 403,
                             'NO_ES_ANFITRION')

    def test_deja_los_eventos_de_reproduccion_y_cola(self):
        self.iniciar()
        tipos = list(EventoSalida.objects.filter(tipo__in=['reproduccion.estado',
                                                           'cola.actualizada'])
                     .order_by('creado_en').values_list('tipo', flat=True))
        self.assertIn('reproduccion.estado', tipos)
        self.assertEqual(tipos.count('cola.actualizada'), 4)

    def test_reintento_no_inicia_otra_vez(self):
        clave = uuid.uuid4()
        primera = self.reproducir('iniciar', clave=clave).json()
        segunda = self.reproducir('iniciar', clave=clave)
        self.assertEqual(segunda.status_code, 200)
        self.assertEqual(segunda.json()['version'], primera['version'])


class PausarReanudarBuscarTests(PruebasReproduccion):

    def setUp(self):
        super().setUp()
        self.iniciar()

    def test_pausar_congela_la_posicion(self):
        self.adelantar_reloj(10)
        estado = self.reproducir('pausar', self.a).json()
        self.assertEqual(estado['estado'], 'pausada')
        # 10 s minus the 1.5 s start lead, with some margin for the test itself.
        self.assertAlmostEqual(estado['posicion_base_ms'], 8500, delta=300)

    def test_pausar_durante_el_adelanto_queda_en_cero(self):
        self.assertEqual(self.reproducir('pausar', self.a).json()['posicion_base_ms'], 0)

    def test_reanudar_sigue_desde_la_posicion_pausada(self):
        self.adelantar_reloj(10)
        pausada = self.reproducir('pausar', self.a).json()
        estado = self.reproducir('reanudar', self.a).json()
        self.assertEqual((estado['estado'], estado['posicion_base_ms']),
                         ('reproduciendo', pausada['posicion_base_ms']))

    def test_buscar_cambia_la_posicion(self):
        estado = self.reproducir('buscar', self.a, 60000).json()
        self.assertEqual((estado['estado'], estado['posicion_base_ms']), ('reproduciendo', 60000))

    def test_buscar_en_pausa_sigue_en_pausa(self):
        self.reproducir('pausar', self.a)
        estado = self.reproducir('buscar', self.a, 30000).json()
        self.assertEqual((estado['estado'], estado['posicion_base_ms']), ('pausada', 30000))

    def test_buscar_sin_posicion(self):
        self.verificar_error(self.reproducir('buscar', self.a), 400, 'DATOS_INVALIDOS')

    def test_con_permiso_de_modificar_no_puede_pausar(self):
        self.verificar_error(self.reproducir('pausar', self.a, usuario_id=self.modificador_id),
                             403, 'NO_ES_ANFITRION')

    def test_pausar_otra_cancion_es_elemento_no_actual(self):
        self.verificar_error(self.reproducir('pausar', self.b), 409, 'ELEMENTO_NO_ACTUAL')

    def test_accion_que_no_existe(self):
        self.verificar_error(self.reproducir('votar', self.a), 400, 'DATOS_INVALIDOS')


class SaltarTests(PruebasReproduccion):

    def setUp(self):
        super().setUp()
        self.iniciar()

    def test_omite_la_actual_y_empieza_la_siguiente(self):
        estado = self.reproducir('saltar', self.a).json()
        self.assertEqual((estado['elemento_id'], estado['posicion_base_ms']), (self.b, 0))
        self.assertEqual(self.estado_de(self.a), 'omitida')

    def test_saltar_durante_el_adelanto_no_rompe_la_base(self):
        # fin_en cannot precede referencia_en, which is still in the future here.
        self.assertEqual(self.reproducir('saltar', self.a).status_code, 200)

    def test_saltar_la_ultima_detiene(self):
        self.reproducir('saltar', self.a)
        self.reproducir('saltar', self.b)
        estado = self.reproducir('saltar', self.c).json()
        self.assertEqual((estado['estado'], estado['elemento_id']), ('detenida', None))
        self.assertIsNone(self.consultar().json()['actual'])

    def test_con_permiso_de_modificar_puede(self):
        respuesta = self.reproducir('saltar', self.a, usuario_id=self.modificador_id)
        self.assertEqual(respuesta.status_code, 200)

    def test_oyente_sin_permiso_no_puede(self):
        self.verificar_error(self.reproducir('saltar', self.a, usuario_id=self.oyente_id), 403,
                             'SIN_PERMISO')

    def test_saltar_una_cancion_que_ya_no_suena(self):
        self.reproducir('saltar', self.a)
        self.verificar_error(self.reproducir('saltar', self.a), 409, 'ELEMENTO_NO_ACTUAL')
        self.assertEqual(self.estado_de(self.b), 'reproduciendo')


class TerminadaTests(PruebasReproduccion):

    def setUp(self):
        super().setUp()
        self.iniciar()

    def test_avanza_a_la_siguiente(self):
        estado = self.terminar(self.a).json()
        self.assertEqual(estado['elemento_id'], self.b)
        self.assertEqual(self.estado_de(self.a), 'reproducida')

    def test_aviso_duplicado_no_avanza_dos_veces(self):
        self.terminar(self.a)
        estado = self.terminar(self.a).json()
        self.assertEqual(estado['elemento_id'], self.b)
        self.assertEqual(self.estado_de(self.b), 'reproduciendo')

    def test_la_ultima_detiene(self):
        self.terminar(self.a)
        self.terminar(self.b)
        self.assertEqual(self.terminar(self.c).json()['estado'], 'detenida')

    def test_solo_el_anfitrion_mientras_no_haya_duracion(self):
        self.verificar_error(self.terminar(self.a, self.modificador_id), 403, 'NO_ES_ANFITRION')


class SaltosSimultaneosTests(PruebasColaConcurrentes):
    """Criterio de T-34: dos saltos a la vez omiten una sola canción."""

    def test_dos_saltos_a_la_vez_omiten_una_sola(self):
        for _ in range(3):
            estado = self.agregar().json()
        a, b, _ = self.ids_pendientes(estado)
        self.reproducir('iniciar')
        codigos = []

        def saltar(usuario_id):
            codigos.append(self.reproducir('saltar', a, usuario_id=usuario_id).status_code)
            connection.close()

        hilos = [threading.Thread(target=saltar, args=(u,))
                 for u in (self.anfitrion_id, self.modificador_id)]
        for hilo in hilos:
            hilo.start()
        for hilo in hilos:
            hilo.join()

        self.assertEqual(sorted(codigos), [200, 409])
        self.assertEqual(ElementoCola.objects.get(id=b).estado, 'reproduciendo')
