import threading
import uuid

from django.db import connection

from apps.musicqueue.models import Cola, ElementoCola, EventoSalida
from .utilidades import PruebasCola, PruebasColaConcurrentes


class ConsultarColaTests(PruebasCola):

    def test_cola_nueva_esta_vacia(self):
        respuesta = self.consultar()
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json()['modalidad'], 'compartida')
        self.assertEqual((respuesta.json()['version'], respuesta.json()['actual'],
                          respuesta.json()['pendientes']), (0, None, []))

    def test_consultar_dos_veces_no_crea_otra_cola(self):
        self.consultar()
        self.consultar()
        self.assertEqual(Cola.objects.filter(party_id=self.party_id).count(), 1)

    def test_pasa_el_token_del_usuario_a_party(self):
        self.consultar(self.oyente_id)
        token, party_id = self.consultar_party.call_args.args
        self.assertEqual(party_id, self.party_id)
        self.assertTrue(token)


class AgregarTests(PruebasCola):

    def test_se_agrega_al_final_y_sube_la_version(self):
        primera = self.agregar().json()
        segunda = self.agregar().json()
        self.assertEqual(segunda['version'], 2)
        self.assertEqual(len(segunda['pendientes']), 2)
        self.assertEqual(segunda['pendientes'][0]['id'], primera['pendientes'][0]['id'])

    def test_responde_201_con_la_cancion(self):
        recurso = uuid.uuid4()
        respuesta = self.agregar(recurso=recurso)
        self.assertEqual(respuesta.status_code, 201)
        elemento = respuesta.json()['pendientes'][0]
        self.assertEqual((elemento['recurso_audio_id'], elemento['agregado_por'],
                          elemento['estado']), (str(recurso), str(self.anfitrion_id), 'pendiente'))

    def test_no_inicia_la_reproduccion(self):
        self.assertIsNone(self.agregar().json()['actual'])

    def test_la_misma_cancion_puede_estar_dos_veces(self):
        recurso = uuid.uuid4()
        self.agregar(recurso=recurso)
        self.assertEqual(len(self.agregar(recurso=recurso).json()['pendientes']), 2)

    def test_con_permiso_de_aportar_puede(self):
        self.assertEqual(self.agregar(self.aportador_id).status_code, 201)

    def test_oyente_sin_permiso_no_puede(self):
        self.verificar_error(self.agregar(self.oyente_id), 403, 'SIN_PERMISO')

    def test_permiso_de_modificar_no_basta_para_agregar(self):
        self.verificar_error(self.agregar(self.modificador_id), 403, 'SIN_PERMISO')

    def test_reintento_con_la_misma_clave_no_duplica(self):
        clave, recurso = uuid.uuid4(), uuid.uuid4()
        self.agregar(clave=clave, recurso=recurso)
        respuesta = self.agregar(clave=clave, recurso=recurso)
        self.assertEqual(respuesta.status_code, 201)
        self.assertEqual(len(respuesta.json()['pendientes']), 1)
        self.assertEqual(respuesta.json()['version'], 1)

    def test_misma_clave_con_otra_cancion_es_conflicto(self):
        clave = uuid.uuid4()
        self.agregar(clave=clave)
        self.verificar_error(self.agregar(clave=clave), 409, 'IDEMPOTENCIA_CONFLICTO')

    def test_sin_clave_de_idempotencia(self):
        respuesta = self.cliente.post(
            f'{self.url}/elementos', {'recurso_audio_id': str(uuid.uuid4())}, format='json',
            HTTP_AUTHORIZATION=self.cabeceras(self.anfitrion_id)['HTTP_AUTHORIZATION'])
        self.verificar_error(respuesta, 400, 'DATOS_INVALIDOS')

    def test_cancion_que_no_es_uuid(self):
        respuesta = self.cliente.post(f'{self.url}/elementos', {'recurso_audio_id': 'x'},
                                      format='json', **self.cabeceras(self.anfitrion_id))
        self.verificar_error(respuesta, 400, 'DATOS_INVALIDOS')

    def test_deja_el_evento_cola_actualizada(self):
        estado = self.agregar().json()
        evento = EventoSalida.objects.get()
        self.assertEqual((evento.tipo, evento.version, evento.datos),
                         ('cola.actualizada', 1, estado))

    def test_error_de_party_llega_igual_al_cliente(self):
        from apps.parties.errores import ErrorApi
        self.consultar_party.side_effect = ErrorApi(403, 'NO_ES_MIEMBRO', 'No estás dentro.')
        self.verificar_error(self.agregar(), 403, 'NO_ES_MIEMBRO')
        self.assertFalse(ElementoCola.objects.exists())

    def test_sin_token(self):
        respuesta = self.cliente.get(self.url)
        self.verificar_error(respuesta, 401, 'TOKEN_INVALIDO')


class ReordenarTests(PruebasCola):

    def setUp(self):
        super().setUp()
        for _ in range(3):
            estado = self.agregar().json()
        self.a, self.b, self.c = self.ids_pendientes(estado)
        self.version = estado['version']

    def test_mueve_al_principio(self):
        estado = self.reordenar(self.c, 1, self.version).json()
        self.assertEqual(self.ids_pendientes(estado), [self.c, self.a, self.b])
        self.assertEqual(estado['version'], self.version + 1)

    def test_mueve_al_final(self):
        estado = self.reordenar(self.a, 3, self.version).json()
        self.assertEqual(self.ids_pendientes(estado), [self.b, self.c, self.a])

    def test_a_la_misma_posicion_no_cambia_el_orden(self):
        estado = self.reordenar(self.b, 2, self.version).json()
        self.assertEqual(self.ids_pendientes(estado), [self.a, self.b, self.c])

    def test_version_obsoleta(self):
        respuesta = self.reordenar(self.c, 1, self.version - 1)
        self.verificar_error(respuesta, 409, 'VERSION_OBSOLETA')
        self.assertEqual(respuesta.json()['detalles'], {'version_actual': self.version})

    def test_reintento_tras_exito_no_choca_con_su_propia_version(self):
        clave = uuid.uuid4()
        self.reordenar(self.c, 1, self.version, clave=clave)
        respuesta = self.reordenar(self.c, 1, self.version, clave=clave)
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json()['version'], self.version + 1)

    def test_posicion_fuera_de_rango(self):
        self.verificar_error(self.reordenar(self.a, 4, self.version), 400, 'DATOS_INVALIDOS')
        self.verificar_error(self.reordenar(self.a, 0, self.version), 400, 'DATOS_INVALIDOS')

    def test_version_que_no_es_entero(self):
        self.verificar_error(self.reordenar(self.a, 1, True), 400, 'DATOS_INVALIDOS')

    def test_elemento_que_no_existe(self):
        self.verificar_error(self.reordenar(uuid.uuid4(), 1, self.version), 404, 'NO_ENCONTRADO')

    def test_elemento_retirado_no_se_mueve(self):
        version = self.retirar(self.a, self.version).json()['version']
        self.verificar_error(self.reordenar(self.a, 1, version), 409, 'ELEMENTO_NO_PENDIENTE')

    def test_actual_no_se_mueve(self):
        elemento = ElementoCola.objects.get(id=self.a)
        ElementoCola.objects.filter(id=self.a).update(estado='reproduciendo',
                                                      inicio_en=elemento.agregado_en,
                                                      referencia_en=elemento.agregado_en)
        self.verificar_error(self.reordenar(self.a, 2, self.version), 409, 'ELEMENTO_NO_PENDIENTE')

    def test_con_permiso_de_modificar_puede(self):
        self.assertEqual(self.reordenar(self.c, 1, self.version, self.modificador_id).status_code,
                         200)

    def test_permiso_de_aportar_no_basta_para_mover(self):
        self.verificar_error(self.reordenar(self.c, 1, self.version, self.aportador_id), 403,
                             'SIN_PERMISO')


class RetirarTests(PruebasCola):

    def setUp(self):
        super().setUp()
        estado = self.agregar().json()
        estado = self.agregar().json()
        self.a, self.b = self.ids_pendientes(estado)
        self.version = estado['version']

    def test_retira_y_conserva_el_historial(self):
        estado = self.retirar(self.a, self.version).json()
        self.assertEqual(self.ids_pendientes(estado), [self.b])
        elemento = ElementoCola.objects.get(id=self.a)
        self.assertEqual(elemento.estado, 'retirada')
        self.assertIsNotNone(elemento.fin_en)

    def test_retirar_dos_veces_con_otra_clave(self):
        version = self.retirar(self.a, self.version).json()['version']
        self.verificar_error(self.retirar(self.a, version), 409, 'ELEMENTO_NO_PENDIENTE')

    def test_version_obsoleta(self):
        self.verificar_error(self.retirar(self.a, self.version + 5), 409, 'VERSION_OBSOLETA')

    def test_sin_version(self):
        respuesta = self.cliente.delete(f'{self.url}/elementos/{self.a}',
                                        **self.cabeceras(self.anfitrion_id))
        self.verificar_error(respuesta, 400, 'DATOS_INVALIDOS')

    def test_oyente_sin_permiso_no_puede(self):
        self.verificar_error(self.retirar(self.a, self.version, self.oyente_id), 403,
                             'SIN_PERMISO')

    def test_agregar_despues_de_retirar_va_al_final(self):
        self.retirar(self.b, self.version)
        estado = self.agregar().json()
        ordenes = [e['orden'] for e in estado['pendientes']]
        self.assertEqual(ordenes, sorted(ordenes))
        self.assertEqual(len(set(ordenes)), 2)


class AgregadosSimultaneosTests(PruebasColaConcurrentes):
    """Sin bloquear la cola, dos agregados leen el mismo último orden y uno falla."""

    def test_diez_agregados_a_la_vez_quedan_todos_en_orden(self):
        codigos = []

        def agregar():
            codigos.append(self.agregar().status_code)
            connection.close()

        hilos = [threading.Thread(target=agregar) for _ in range(10)]
        for hilo in hilos:
            hilo.start()
        for hilo in hilos:
            hilo.join()

        self.assertEqual(codigos, [201] * 10)
        cola = Cola.objects.get(party_id=self.party_id)
        ordenes = sorted(ElementoCola.objects.filter(cola=cola).values_list('orden', flat=True))
        self.assertEqual((ordenes, cola.version), (list(range(1, 11)), 10))
