import uuid

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.musicqueue.models import Cola, ElementoCola, EventoSalida
from .utilidades import CLAVE_PUBLICA, hacer_token

URL = '/api/v1/queue/mi-cola'


@override_settings(JWT_CLAVE_PUBLICA=CLAVE_PUBLICA)
class PruebasMiCola(TestCase):

    def setUp(self):
        self.cliente = APIClient()
        self.usuario_id = uuid.uuid4()
        self.otro_id = uuid.uuid4()

    def cabeceras(self, usuario_id=None, clave=None):
        return {'HTTP_AUTHORIZATION': f'Bearer {hacer_token(usuario_id or self.usuario_id)}',
                'HTTP_IDEMPOTENCY_KEY': str(clave or uuid.uuid4())}

    def consultar(self, usuario_id=None):
        return self.cliente.get(URL, **self.cabeceras(usuario_id))

    def agregar(self, usuario_id=None, recurso=None, clave=None):
        return self.cliente.post(f'{URL}/elementos',
                                 {'recurso_audio_id': str(recurso or uuid.uuid4())},
                                 format='json', **self.cabeceras(usuario_id, clave))

    def reordenar(self, elemento_id, posicion, version, usuario_id=None):
        return self.cliente.patch(f'{URL}/elementos/{elemento_id}',
                                  {'nueva_posicion': posicion, 'version_esperada': version},
                                  format='json', **self.cabeceras(usuario_id))

    def retirar(self, elemento_id, version, usuario_id=None):
        return self.cliente.delete(f'{URL}/elementos/{elemento_id}?version_esperada={version}',
                                   **self.cabeceras(usuario_id))

    def reproducir(self, accion, elemento_id=None, posicion_ms=None, usuario_id=None):
        cuerpo = {'accion': accion, 'elemento_id': str(elemento_id) if elemento_id else None,
                  'posicion_ms': posicion_ms}
        return self.cliente.post(f'{URL}/reproduccion', cuerpo, format='json',
                                 **self.cabeceras(usuario_id))

    def terminar(self, elemento_id, usuario_id=None):
        return self.cliente.post(f'{URL}/elementos/{elemento_id}/terminada',
                                 **self.cabeceras(usuario_id))

    def verificar_error(self, respuesta, estado, codigo):
        self.assertEqual((respuesta.status_code, respuesta.json()['codigo']), (estado, codigo))

    def agregar_tres(self):
        for _ in range(3):
            estado = self.agregar().json()
        return [e['id'] for e in estado['pendientes']]


class ConsultarMiColaTests(PruebasMiCola):

    def test_cola_nueva_es_individual_y_vacia(self):
        respuesta = self.consultar()
        self.assertEqual(respuesta.status_code, 200)
        estado = respuesta.json()
        self.assertEqual((estado['modalidad'], estado['version'], estado['actual'],
                          estado['pendientes']), ('individual', 0, None, []))

    def test_se_crea_una_sola_vez_por_usuario(self):
        self.consultar()
        self.consultar()
        self.assertEqual(Cola.objects.filter(usuario_id=self.usuario_id).count(), 1)

    def test_sin_token_es_rechazado(self):
        self.verificar_error(self.cliente.get(URL), 401, 'TOKEN_INVALIDO')

    def test_cada_usuario_ve_solo_la_suya(self):
        self.agregar()
        self.assertEqual(self.consultar(self.otro_id).json()['pendientes'], [])

    def test_se_conserva_entre_sesiones(self):
        recurso = uuid.uuid4()
        self.agregar(recurso=recurso)
        # A new token is a new session: the queue belongs to the user, not to the token.
        pendientes = self.consultar().json()['pendientes']
        self.assertEqual([p['recurso_audio_id'] for p in pendientes], [str(recurso)])


class AgregarAMiColaTests(PruebasMiCola):

    def test_se_agrega_al_final_sin_iniciar(self):
        recurso = uuid.uuid4()
        self.agregar()
        respuesta = self.agregar(recurso=recurso)
        self.assertEqual(respuesta.status_code, 201)
        estado = respuesta.json()
        self.assertEqual(estado['pendientes'][-1]['recurso_audio_id'], str(recurso))
        self.assertIsNone(estado['actual'])
        self.assertEqual(estado['version'], 2)

    def test_reintento_con_la_misma_clave_no_duplica(self):
        clave, recurso = uuid.uuid4(), uuid.uuid4()
        self.agregar(clave=clave, recurso=recurso)
        respuesta = self.agregar(clave=clave, recurso=recurso)
        self.assertEqual(len(respuesta.json()['pendientes']), 1)

    def test_no_publica_eventos_para_otros(self):
        self.agregar()
        self.assertFalse(EventoSalida.objects.exists())

    def test_recurso_invalido(self):
        respuesta = self.cliente.post(f'{URL}/elementos', {'recurso_audio_id': 'x'},
                                      format='json', **self.cabeceras())
        self.verificar_error(respuesta, 400, 'DATOS_INVALIDOS')


class ReordenarYRetirarTests(PruebasMiCola):

    def test_mover_la_ultima_al_principio(self):
        a, b, c = self.agregar_tres()
        estado = self.reordenar(c, 1, 3).json()
        self.assertEqual([e['id'] for e in estado['pendientes']], [c, a, b])

    def test_version_vieja_es_rechazada(self):
        a, _, _ = self.agregar_tres()
        self.verificar_error(self.reordenar(a, 2, 1), 409, 'VERSION_OBSOLETA')

    def test_retirar_la_quita_de_pendientes(self):
        a, b, c = self.agregar_tres()
        estado = self.retirar(b, 3).json()
        self.assertEqual([e['id'] for e in estado['pendientes']], [a, c])
        self.assertEqual(ElementoCola.objects.get(id=b).estado, 'retirada')

    def test_otro_usuario_no_toca_mi_cola(self):
        a, _, _ = self.agregar_tres()
        # The other user's own queue is empty, so the item does not exist there.
        self.verificar_error(self.retirar(a, 0, usuario_id=self.otro_id), 404, 'NO_ENCONTRADO')
        self.assertEqual(ElementoCola.objects.get(id=a).estado, 'pendiente')


class MiReproduccionTests(PruebasMiCola):

    def test_iniciar_pausar_y_reanudar_las_hace_el_dueno(self):
        a, _, _ = self.agregar_tres()
        self.assertEqual(self.reproducir('iniciar').json()['elemento_id'], a)
        self.assertEqual(self.reproducir('pausar', a).json()['estado'], 'pausada')
        self.assertEqual(self.reproducir('reanudar', a).json()['estado'], 'reproduciendo')

    def test_arranca_sin_adelanto(self):
        self.agregar()
        self.reproducir('iniciar')
        actual = ElementoCola.objects.get(estado='reproduciendo')
        self.assertEqual(actual.referencia_en, actual.inicio_en)

    def test_saltar_empieza_la_siguiente(self):
        a, b, _ = self.agregar_tres()
        self.reproducir('iniciar')
        self.assertEqual(self.reproducir('saltar', a).json()['elemento_id'], b)
        self.assertEqual(ElementoCola.objects.get(id=a).estado, 'omitida')

    def test_iniciar_con_la_cola_vacia(self):
        self.verificar_error(self.reproducir('iniciar'), 409, 'COLA_VACIA')

    def test_terminar_avanza_una_sola_vez(self):
        a, b, c = self.agregar_tres()
        self.reproducir('iniciar')
        self.assertEqual(self.terminar(a).json()['elemento_id'], b)
        # A repeated end notice for the same song must not skip b.
        self.assertEqual(self.terminar(a).json()['elemento_id'], b)
        self.assertEqual(ElementoCola.objects.get(id=c).estado, 'pendiente')

    def test_al_terminar_la_ultima_se_detiene(self):
        self.agregar()
        actual = self.reproducir('iniciar').json()['elemento_id']
        self.assertEqual(self.terminar(actual).json()['estado'], 'detenida')

    def test_no_cambia_la_cola_de_ninguna_party(self):
        self.agregar()
        self.reproducir('iniciar')
        self.assertFalse(Cola.objects.filter(party_id__isnull=False).exists())
