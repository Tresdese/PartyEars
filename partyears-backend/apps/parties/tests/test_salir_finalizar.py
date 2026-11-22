import uuid
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import patch

from channels.db import database_sync_to_async
from channels.routing import URLRouter
from channels.testing import WebsocketCommunicator
from django.test import TransactionTestCase, override_settings

from apps.parties.models import (AnfitrionParty, EventoSalida, MiembroParty, ParticipacionParty, Party)
from apps.parties.routing import websocket_urlpatterns
from apps.parties.servicios import finalizar_party, salir_party
from .test_websocket import token
from .utilidades import (CLAVE_PUBLICA, PruebasBase, agregar_miembro, crear_party_en_bd, hacer_token, vaciar_tablas_party)


class PruebasSalida(PruebasBase):
    URL_UNIRSE = '/api/v1/party/parties/unirse'

    def setUp(self):
        super().setUp()
        self.anfitrion_id = uuid.uuid4()
        estado = self.crear(self.anfitrion_id).json()
        self.party_id = uuid.UUID(estado['id'])
        self.codigo = estado['codigo']

    def post(self, accion, usuario_id, party_id=None, clave=None):
        cabeceras = {'HTTP_AUTHORIZATION': f'Bearer {hacer_token(usuario_id)}'}
        if clave != 'sin_clave':
            cabeceras['HTTP_IDEMPOTENCY_KEY'] = str(clave or uuid.uuid4())
        return self.cliente.post(f'{self.URL}/{party_id or self.party_id}/{accion}', {}, format='json', **cabeceras)

    def salir(self, usuario_id, **kwargs):
        return self.post('salir', usuario_id, **kwargs)

    def finalizar(self, usuario_id, **kwargs):
        return self.post('finalizar', usuario_id, **kwargs)

    def unirse(self, usuario_id, codigo=None):
        return self.cliente.post(
            self.URL_UNIRSE, {'codigo': codigo or self.codigo}, format='json',
            HTTP_AUTHORIZATION=f'Bearer {hacer_token(usuario_id)}',
            HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))

    def party(self):
        return Party.objects.get(id=self.party_id)

    def anfitrion(self):
        return AnfitrionParty.objects.get(party_id=self.party_id).usuario_id

    def participacion(self, usuario_id):
        return ParticipacionParty.objects.filter(party_id=self.party_id, usuario_id=usuario_id).order_by('-entrada_en').first()

    def tipos_de_eventos(self):
        eventos = EventoSalida.objects.filter(agregado_id=self.party_id).order_by('version')
        return [(e.tipo, e.version) for e in eventos]

    def agregar(self, esta_conectado=True, estado='habilitado'):
        usuario_id = uuid.uuid4()
        agregar_miembro(self.party_id, usuario_id, esta_conectado)
        if estado != 'habilitado':
            MiembroParty.objects.filter(usuario_id=usuario_id).update(estado=estado)
        return usuario_id

    def verificar_error(self, respuesta, estado, codigo):
        self.assertEqual((respuesta.status_code, respuesta.json()['codigo']), (estado, codigo))


class SalirTests(PruebasSalida):

    def test_un_miembro_sale_y_la_party_continua(self):
        miembro = self.agregar()
        version = self.party().version

        respuesta = self.salir(miembro)

        self.assertEqual(respuesta.status_code, 204)
        participacion = self.participacion(miembro)
        self.assertIsNotNone(participacion.salida_en)
        self.assertEqual(participacion.motivo_salida, 'voluntaria')
        self.assertIsNone(self.party().finalizada_en)
        self.assertEqual(self.anfitrion(), self.anfitrion_id)
        self.assertEqual(self.party().version, version + 1)

    def test_deja_el_evento_de_salida_con_la_nueva_version(self):
        miembro = self.agregar()
        version = self.party().version
        self.salir(miembro)
        evento = EventoSalida.objects.get(agregado_id=self.party_id, tipo='miembro.salida')
        self.assertEqual(evento.version, version + 1)
        self.assertEqual(evento.datos, {'usuario_id': str(miembro), 'motivo': 'voluntaria'})

    def test_el_miembro_conserva_su_registro_pero_ya_no_esta_conectado(self):
        miembro = self.agregar()
        self.salir(miembro)
        estado = self.cliente.get(f'{self.URL}/{self.party_id}', HTTP_AUTHORIZATION=f'Bearer {hacer_token(self.anfitrion_id)}').json()
        datos = next(m for m in estado['miembros'] if m['usuario_id'] == str(miembro))
        self.assertFalse(datos['conectado'])
        self.assertIsNone(datos['orden_ingreso'])

    def test_quien_salio_ya_no_puede_consultar_la_party_ni_tiene_party_actual(self):
        miembro = self.agregar()
        self.salir(miembro)
        respuesta = self.cliente.get(f'{self.URL}/{self.party_id}', HTTP_AUTHORIZATION=f'Bearer {hacer_token(miembro)}')
        self.verificar_error(respuesta, 403, 'NO_ES_MIEMBRO')
        self.assertEqual(self.consultar_actual(miembro).status_code, 204)

    def test_quien_salio_puede_volver_a_unirse_como_oyente(self):
        miembro = self.agregar()
        MiembroParty.objects.filter(usuario_id=miembro).update(puede_aportar=True)
        self.salir(miembro)
        respuesta = self.unirse(miembro)
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(MiembroParty.objects.get(usuario_id=miembro).puede_aportar)

    def test_quien_no_esta_dentro_recibe_no_es_miembro(self):
        self.verificar_error(self.salir(uuid.uuid4()), 403, 'NO_ES_MIEMBRO')

    def test_quien_ya_salio_con_otra_clave_recibe_no_es_miembro(self):
        miembro = self.agregar()
        self.assertEqual(self.salir(miembro).status_code, 204)
        self.verificar_error(self.salir(miembro), 403, 'NO_ES_MIEMBRO')

    def test_party_que_no_existe(self):
        self.verificar_error(self.salir(self.anfitrion_id, party_id=uuid.uuid4()), 404, 'NO_ENCONTRADO')

    def test_party_finalizada(self):
        miembro = self.agregar()
        self.finalizar(self.anfitrion_id)
        self.verificar_error(self.salir(miembro), 410, 'PARTY_FINALIZADA')

    def test_exige_la_clave_de_idempotencia_y_el_token(self):
        self.verificar_error(self.salir(self.anfitrion_id, clave='sin_clave'), 400, 'DATOS_INVALIDOS')
        respuesta = self.cliente.post(f'{self.URL}/{self.party_id}/salir', {}, format='json', HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))
        self.assertEqual(respuesta.status_code, 401)

    def test_avisa_por_websocket_al_confirmar(self):
        miembro = self.agregar()
        version = self.party().version
        with patch('apps.parties.servicios.publicar') as publicar, \
                self.captureOnCommitCallbacks(execute=True):
            self.salir(miembro)
        self.assertEqual(publicar.call_args.args,
                         (str(self.party_id), 'miembro.salida',
                          {'usuario_id': str(miembro), 'motivo': 'voluntaria'}, version + 1))
        evento = EventoSalida.objects.get(tipo='miembro.salida')
        self.assertEqual(publicar.call_args.kwargs['evento_id'], evento.id)

    def test_si_redis_falla_la_salida_sigue_valiendo(self):
        miembro = self.agregar()
        with patch('apps.parties.servicios.publicar', side_effect=ConnectionError), \
                self.assertLogs('apps.parties.servicios', 'ERROR'), \
                self.captureOnCommitCallbacks(execute=True):
            respuesta = self.salir(miembro)
        self.assertEqual(respuesta.status_code, 204)
        self.assertIsNotNone(self.participacion(miembro).salida_en)


class SucesionAlSalirTests(PruebasSalida):

    def test_si_sale_el_anfitrion_el_cargo_pasa_al_primero_por_ingreso(self):
        primero = self.agregar()
        self.agregar()
        version = self.party().version

        self.assertEqual(self.salir(self.anfitrion_id).status_code, 204)

        self.assertEqual(self.anfitrion(), primero)
        self.assertIsNone(self.party().finalizada_en)
        eventos = EventoSalida.objects.get(agregado_id=self.party_id, tipo='anfitrion.cambio')
        self.assertEqual(eventos.datos, {'anterior_id': str(self.anfitrion_id), 'nuevo_id': str(primero), 'motivo': 'sucesion'})
        self.assertEqual(self.tipos_de_eventos()[-3:],
                         [('miembro.salida', version + 1), ('anfitrion.cambio', version + 2), ('miembro.permisos', version + 3)])
        self.assertEqual(self.party().version, version + 3)

    def test_el_nuevo_anfitrion_recibe_todos_los_permisos(self):
        primero = self.agregar()
        self.salir(self.anfitrion_id)
        miembro = MiembroParty.objects.get(usuario_id=primero)
        self.assertEqual((miembro.puede_aportar, miembro.puede_modificar_cola), (True, True))
        evento = EventoSalida.objects.get(tipo='miembro.permisos')
        self.assertEqual(evento.datos, {'usuario_id': str(primero), 'puede_aportar': True, 'puede_modificar_cola': True})

    def test_si_el_sucesor_ya_tenia_todos_los_permisos_no_hay_evento_de_permisos(self):
        primero = self.agregar()
        MiembroParty.objects.filter(usuario_id=primero).update(puede_aportar=True, puede_modificar_cola=True)
        self.salir(self.anfitrion_id)
        self.assertFalse(EventoSalida.objects.filter(tipo='miembro.permisos').exists())

    def test_la_sucesion_ignora_a_desconectados_y_expulsados(self):
        self.agregar(esta_conectado=False)
        self.agregar(estado='expulsado')
        elegido = self.agregar()
        self.salir(self.anfitrion_id)
        self.assertEqual(self.anfitrion(), elegido)

    def test_el_orden_lo_da_la_antiguedad_de_la_participacion_actual(self):
        primero = self.agregar()
        segundo = self.agregar()
        self.salir(primero)
        self.unirse(primero)
        self.salir(self.anfitrion_id)
        self.assertEqual(self.anfitrion(), segundo)

    def test_si_sale_un_miembro_que_no_es_anfitrion_el_cargo_no_cambia(self):
        miembro = self.agregar()
        self.salir(miembro)
        self.assertEqual(self.anfitrion(), self.anfitrion_id)
        self.assertFalse(EventoSalida.objects.filter(tipo='anfitrion.cambio').exists())

    def test_el_anfitrion_que_vuelve_entra_como_oyente_y_no_recupera_el_cargo(self):
        primero = self.agregar()
        orden_anterior = self.participacion(self.anfitrion_id).orden_ingreso
        self.salir(self.anfitrion_id)

        self.assertEqual(self.unirse(self.anfitrion_id).status_code, 200)

        self.assertEqual(self.anfitrion(), primero)
        antiguo = MiembroParty.objects.get(usuario_id=self.anfitrion_id)
        self.assertEqual((antiguo.puede_aportar, antiguo.puede_modificar_cola), (False, False))
        self.assertGreater(self.participacion(self.anfitrion_id).orden_ingreso, orden_anterior)
        self.assertEqual(AnfitrionParty.objects.filter(party_id=self.party_id).count(), 1)

    def test_el_anfitrion_anterior_ya_no_puede_finalizar(self):
        self.agregar()
        self.salir(self.anfitrion_id)
        self.unirse(self.anfitrion_id)
        self.verificar_error(self.finalizar(self.anfitrion_id), 403, 'NO_ES_ANFITRION')

    def test_el_nuevo_anfitrion_si_puede_finalizar(self):
        primero = self.agregar()
        self.salir(self.anfitrion_id)
        self.assertEqual(self.finalizar(primero).status_code, 204)


class CierreAutomaticoTests(PruebasSalida):

    def test_si_sale_el_ultimo_conectado_la_party_se_finaliza(self):
        version = self.party().version

        self.assertEqual(self.salir(self.anfitrion_id).status_code, 204)

        party = self.party()
        self.assertIsNotNone(party.finalizada_en)
        self.assertEqual(self.tipos_de_eventos()[-2:], [('miembro.salida', version + 1), ('party.finalizada', version + 2)])
        evento = EventoSalida.objects.get(tipo='party.finalizada')
        self.assertEqual(evento.datos['motivo'], 'sin_conectados')
        self.assertTrue(evento.datos['finalizada_en'].endswith('Z'))
        self.assertEqual(party.version, version + 2)

    def test_el_ultimo_en_salir_cierra_aunque_no_sea_el_anfitrion(self):
        miembro = self.agregar()
        self.salir(self.anfitrion_id)
        self.assertIsNone(self.party().finalizada_en)
        self.salir(miembro)
        self.assertIsNotNone(self.party().finalizada_en)

    def test_miembros_desconectados_no_sostienen_la_party(self):
        self.agregar(esta_conectado=False)
        self.salir(self.anfitrion_id)
        self.assertIsNotNone(self.party().finalizada_en)

    def test_un_expulsado_con_participacion_abierta_no_sostiene_la_party(self):
        expulsado = self.agregar(estado='expulsado')
        self.salir(self.anfitrion_id)
        self.assertIsNotNone(self.party().finalizada_en)
        self.assertEqual(self.participacion(expulsado).motivo_salida, 'fin_party')

    def test_la_party_finalizada_rechaza_ingresos(self):
        self.salir(self.anfitrion_id)
        respuesta = self.unirse(uuid.uuid4())
        self.verificar_error(respuesta, 410, 'PARTY_FINALIZADA')

    def test_nadie_queda_conectado_ni_con_party_actual(self):
        self.salir(self.anfitrion_id)
        self.assertFalse(ParticipacionParty.objects.filter(party_id=self.party_id, salida_en__isnull=True).exists())
        self.assertEqual(self.consultar_actual(self.anfitrion_id).status_code, 204)

    def test_el_anfitrion_puede_crear_otra_party_despues(self):
        self.salir(self.anfitrion_id)
        self.assertEqual(self.crear(self.anfitrion_id).status_code, 201)

    def test_avisa_la_salida_y_el_cierre_en_orden(self):
        with patch('apps.parties.servicios.publicar') as publicar, \
                self.captureOnCommitCallbacks(execute=True):
            self.salir(self.anfitrion_id)
        self.assertEqual([c.args[1] for c in publicar.call_args_list], ['miembro.salida', 'party.finalizada'])


class FinalizarTests(PruebasSalida):

    def test_el_anfitrion_finaliza_la_party(self):
        miembro = self.agregar()
        desconectado = self.agregar(esta_conectado=False)
        version = self.party().version

        respuesta = self.finalizar(self.anfitrion_id)

        self.assertEqual(respuesta.status_code, 204)
        party = self.party()
        self.assertIsNotNone(party.finalizada_en)
        self.assertEqual(party.version, version + 1)
        for usuario_id in (self.anfitrion_id, miembro):
            participacion = self.participacion(usuario_id)
            self.assertEqual((participacion.salida_en is not None, participacion.motivo_salida), (True, 'fin_party'))
        self.assertIsNone(self.participacion(desconectado))
        evento = EventoSalida.objects.get(tipo='party.finalizada')
        self.assertEqual((evento.version, evento.datos['motivo']), (version + 1, 'anfitrion'))

    def test_avisa_a_todos_por_websocket_al_confirmar(self):
        self.agregar()
        with patch('apps.parties.servicios.publicar') as publicar, \
                self.captureOnCommitCallbacks(execute=True):
            self.finalizar(self.anfitrion_id)
        party_id, tipo, datos, _ = publicar.call_args.args
        self.assertEqual((party_id, tipo, datos['motivo']), (str(self.party_id), 'party.finalizada', 'anfitrion'))

    def test_la_party_finalizada_rechaza_ingresos_cambios_y_consultas(self):
        miembro = self.agregar()
        version = self.party().version
        self.finalizar(self.anfitrion_id)

        self.verificar_error(self.unirse(uuid.uuid4()), 410, 'PARTY_FINALIZADA')
        self.verificar_error(self.unirse(miembro), 410, 'PARTY_FINALIZADA')
        consulta = self.cliente.get(f'{self.URL}/{self.party_id}', HTTP_AUTHORIZATION=f'Bearer {hacer_token(miembro)}')
        self.verificar_error(consulta, 410, 'PARTY_FINALIZADA')
        permisos = self.cliente.put(
            f'{self.URL}/{self.party_id}/miembros/{miembro}/permisos',
            {'puede_aportar': True, 'puede_modificar_cola': True, 'version_esperada': version + 1},
            format='json', HTTP_AUTHORIZATION=f'Bearer {hacer_token(self.anfitrion_id)}',
            HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))
        self.verificar_error(permisos, 410, 'PARTY_FINALIZADA')

    def test_nadie_tiene_ya_party_actual(self):
        miembro = self.agregar()
        self.finalizar(self.anfitrion_id)
        for usuario_id in (self.anfitrion_id, miembro):
            self.assertEqual(self.consultar_actual(usuario_id).status_code, 204)

    def test_solo_el_anfitrion_puede_finalizar(self):
        miembro = self.agregar()
        self.verificar_error(self.finalizar(miembro), 403, 'NO_ES_ANFITRION')
        self.assertIsNone(self.party().finalizada_en)
        self.assertIsNone(self.participacion(miembro).salida_en)

    def test_quien_no_esta_dentro_recibe_no_es_miembro(self):
        self.verificar_error(self.finalizar(uuid.uuid4()), 403, 'NO_ES_MIEMBRO')

    def test_party_que_no_existe(self):
        self.verificar_error(self.finalizar(self.anfitrion_id, party_id=uuid.uuid4()), 404, 'NO_ENCONTRADO')

    def test_party_ya_finalizada_con_otra_clave(self):
        self.finalizar(self.anfitrion_id)
        self.verificar_error(self.finalizar(self.anfitrion_id), 410, 'PARTY_FINALIZADA')

    def test_exige_la_clave_de_idempotencia(self):
        self.verificar_error(self.finalizar(self.anfitrion_id, clave='sin_clave'), 400, 'DATOS_INVALIDOS')


class IdempotenciaTests(PruebasSalida):

    def test_repetir_salir_con_la_misma_clave_no_repite_efectos(self):
        miembro = self.agregar()
        clave = uuid.uuid4()
        self.assertEqual(self.salir(miembro, clave=clave).status_code, 204)
        eventos = len(self.tipos_de_eventos())
        version = self.party().version

        self.assertEqual(self.salir(miembro, clave=clave).status_code, 204)

        self.assertEqual((len(self.tipos_de_eventos()), self.party().version), (eventos, version))

    def test_repetir_la_salida_que_cerro_la_party_devuelve_lo_mismo(self):
        clave = uuid.uuid4()
        self.assertEqual(self.salir(self.anfitrion_id, clave=clave).status_code, 204)
        self.assertEqual(self.salir(self.anfitrion_id, clave=clave).status_code, 204)
        self.assertEqual(EventoSalida.objects.filter(tipo='party.finalizada').count(), 1)

    def test_repetir_finalizar_con_la_misma_clave(self):
        clave = uuid.uuid4()
        self.assertEqual(self.finalizar(self.anfitrion_id, clave=clave).status_code, 204)
        self.assertEqual(self.finalizar(self.anfitrion_id, clave=clave).status_code, 204)
        self.assertEqual(EventoSalida.objects.filter(tipo='party.finalizada').count(), 1)

    def test_la_misma_clave_para_otra_accion_es_conflicto(self):
        clave = uuid.uuid4()
        self.assertEqual(self.salir(self.anfitrion_id, clave=clave).status_code, 204)
        self.verificar_error(self.finalizar(self.anfitrion_id, clave=clave), 409, 'IDEMPOTENCIA_CONFLICTO')


class SalidasSimultaneasTests(TransactionTestCase):
    """Dos miembros que salen a la vez no pueden dejar la party abierta y vacía."""

    def tearDown(self):
        vaciar_tablas_party()

    @override_settings(JWT_CLAVE_PUBLICA=CLAVE_PUBLICA)
    def test_si_salen_los_dos_a_la_vez_la_party_queda_finalizada(self):
        from concurrent.futures import ThreadPoolExecutor
        from django.db import connection

        anfitrion_id, miembro_id = uuid.uuid4(), uuid.uuid4()
        party_id = crear_party_en_bd(anfitrion_id)
        agregar_miembro(party_id, miembro_id)

        def salir(usuario_id):
            try:
                usuario = SimpleNamespace(id=usuario_id, nombre_usuario='x')
                return salir_party(usuario, party_id, uuid.uuid4())
            finally:
                connection.close()

        with patch('apps.parties.servicios.publicar'), ThreadPoolExecutor(2) as hilos:
            resultados = list(hilos.map(salir, (anfitrion_id, miembro_id)))

        self.assertEqual(resultados, [(None, 204), (None, 204)])
        self.assertIsNotNone(Party.objects.get(id=party_id).finalizada_en)
        self.assertEqual(EventoSalida.objects.filter(tipo='party.finalizada').count(), 1)


class PruebasWebSocketParty(IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        ajustes = override_settings(
            JWT_CLAVE_PUBLICA=CLAVE_PUBLICA,
            WS_TIEMPO_AUTENTICAR=0.3,
            CHANNEL_LAYERS={'default': {'BACKEND': 'channels.layers.InMemoryChannelLayer'}},
        )
        ajustes.enable()
        self.addCleanup(ajustes.disable)
        self.anfitrion_id = uuid.uuid4()
        self.party_id = await database_sync_to_async(crear_party_en_bd)(self.anfitrion_id)
        self.abiertos = []

    async def asyncTearDown(self):
        for cliente in self.abiertos:
            await cliente.disconnect()
        await database_sync_to_async(vaciar_tablas_party)()

    async def conectar_miembro(self, usuario_id=None):
        usuario_id = usuario_id or uuid.uuid4()
        if usuario_id != self.anfitrion_id:
            await database_sync_to_async(agregar_miembro)(self.party_id, usuario_id)
        cliente = WebsocketCommunicator(URLRouter(websocket_urlpatterns), f'/ws/v1/party/parties/{self.party_id}/')
        await cliente.connect()
        self.abiertos.append(cliente)
        await cliente.send_json_to({'tipo': 'autenticar', 'datos': {'token': token(sub=str(usuario_id))}})
        respuesta = await cliente.receive_json_from(timeout=1)
        self.assertEqual(respuesta['tipo'], 'autenticado')
        return usuario_id, cliente

    async def ejecutar(self, servicio, usuario_id):
        usuario = SimpleNamespace(id=usuario_id, nombre_usuario='x')
        return await database_sync_to_async(servicio)(usuario, self.party_id, uuid.uuid4())

    async def cierre(self, cliente):
        salida = await cliente.receive_output(timeout=1)
        self.assertEqual(salida['type'], 'websocket.close', f'se esperaba un cierre: {salida}')
        return salida.get('code')


class WebSocketSalidaTests(PruebasWebSocketParty):

    async def test_al_finalizar_todos_reciben_el_aviso_y_el_servidor_cierra_con_4010(self):
        _, oyente = await self.conectar_miembro()
        _, anfitrion = await self.conectar_miembro(self.anfitrion_id)

        await self.ejecutar(finalizar_party, self.anfitrion_id)

        for cliente in (oyente, anfitrion):
            evento = await cliente.receive_json_from(timeout=1)
            self.assertEqual(evento['tipo'], 'party.finalizada')
            self.assertEqual(evento['datos']['motivo'], 'anfitrion')
            self.assertEqual(await self.cierre(cliente), 4010)

    async def test_quien_sale_recibe_su_salida_y_el_servidor_cierra_con_4003(self):
        usuario_id, saliente = await self.conectar_miembro()
        _, otro = await self.conectar_miembro()

        await self.ejecutar(salir_party, usuario_id)

        evento = await saliente.receive_json_from(timeout=1)
        self.assertEqual((evento['tipo'], evento['datos']['usuario_id']), ('miembro.salida', str(usuario_id)))
        self.assertEqual(await self.cierre(saliente), 4003)

        evento = await otro.receive_json_from(timeout=1)
        self.assertEqual((evento['tipo'], evento['datos']['motivo']), ('miembro.salida', 'voluntaria'))
        self.assertTrue(await otro.receive_nothing(timeout=0.2))

    async def test_si_sale_el_anfitrion_los_demas_reciben_el_cambio_de_cargo(self):
        sucesor, otro = await self.conectar_miembro()
        _, anfitrion = await self.conectar_miembro(self.anfitrion_id)

        await self.ejecutar(salir_party, self.anfitrion_id)

        tipos = [(await otro.receive_json_from(timeout=1))['tipo'] for _ in range(3)]
        self.assertEqual(tipos, ['miembro.salida', 'anfitrion.cambio', 'miembro.permisos'])
        self.assertEqual((await anfitrion.receive_json_from(timeout=1))['tipo'], 'miembro.salida')
        self.assertEqual(await self.cierre(anfitrion), 4003)
        anfitrion_actual = await database_sync_to_async(
            lambda: AnfitrionParty.objects.get(party_id=self.party_id).usuario_id)()
        self.assertEqual(anfitrion_actual, sucesor)

    async def test_el_ultimo_en_salir_recibe_su_salida_y_la_party_queda_finalizada(self):
        _, anfitrion = await self.conectar_miembro(self.anfitrion_id)

        await self.ejecutar(salir_party, self.anfitrion_id)

        self.assertEqual((await anfitrion.receive_json_from(timeout=1))['tipo'], 'miembro.salida')
        self.assertEqual(await self.cierre(anfitrion), 4003)
        finalizada = await database_sync_to_async(lambda: Party.objects.get(id=self.party_id).finalizada_en)()
        self.assertIsNotNone(finalizada)