import uuid
from types import SimpleNamespace

from channels.db import database_sync_to_async

from apps.parties.models import MiembroParty, ParticipacionParty, Party
from apps.parties.servicios import expulsar_miembro
from .test_salir_finalizar import PruebasSalida, PruebasWebSocketParty
from .utilidades import hacer_token


class PruebasExpulsion(PruebasSalida):

    def administrar(self, accion, miembro_id, usuario_id=None, version=None, clave=None,
                    cuerpo=None):
        cabeceras = {'HTTP_AUTHORIZATION': f'Bearer {hacer_token(usuario_id or self.anfitrion_id)}'}
        if clave != 'sin_clave':
            cabeceras['HTTP_IDEMPOTENCY_KEY'] = str(clave or uuid.uuid4())
        if cuerpo is None:
            cuerpo = {'version_esperada': self.party().version if version is None else version}
        return self.cliente.post(f'{self.URL}/{self.party_id}/miembros/{miembro_id}/{accion}',
                                 cuerpo, format='json', **cabeceras)

    def expulsar(self, miembro_id, **kwargs):
        return self.administrar('expulsar', miembro_id, **kwargs)

    def rehabilitar(self, miembro_id, **kwargs):
        return self.administrar('rehabilitar', miembro_id, **kwargs)

    def miembro(self, usuario_id):
        return MiembroParty.objects.get(party_id=self.party_id, usuario_id=usuario_id)

    def consultar(self, usuario_id):
        return self.cliente.get(f'{self.URL}/{self.party_id}',
                                HTTP_AUTHORIZATION=f'Bearer {hacer_token(usuario_id)}')


class ExpulsarTests(PruebasExpulsion):

    def test_expulsar_cierra_la_participacion_y_quita_los_permisos(self):
        miembro = self.agregar()
        MiembroParty.objects.filter(usuario_id=miembro).update(puede_aportar=True)
        version = self.party().version

        respuesta = self.expulsar(miembro)

        self.assertEqual(respuesta.status_code, 204)
        fila = self.miembro(miembro)
        self.assertEqual((fila.estado, fila.puede_aportar, fila.puede_modificar_cola),
                         ('expulsado', False, False))
        participacion = self.participacion(miembro)
        self.assertEqual((participacion.salida_en is not None, participacion.motivo_salida),
                         (True, 'expulsion'))
        self.assertEqual(self.tipos_de_eventos()[-2:],
                         [('miembro.expulsado', version + 1), ('miembro.salida', version + 2)])
        self.assertEqual(self.party().version, version + 2)

    def test_el_expulsado_no_puede_volver_ni_consultar(self):
        miembro = self.agregar()
        self.expulsar(miembro)

        self.verificar_error(self.unirse(miembro), 403, 'USUARIO_EXPULSADO')
        self.verificar_error(self.consultar(miembro), 403, 'NO_ES_MIEMBRO')

    def test_expulsar_a_un_desconectado_solo_avisa_la_expulsion(self):
        miembro = self.agregar(esta_conectado=False)
        version = self.party().version

        self.assertEqual(self.expulsar(miembro).status_code, 204)

        self.assertEqual(self.tipos_de_eventos()[-1], ('miembro.expulsado', version + 1))
        self.assertEqual(self.party().version, version + 1)

    def test_expulsar_al_ultimo_conectado_finaliza_la_party(self):
        miembro = self.agregar()
        ParticipacionParty.objects.filter(usuario_id=self.anfitrion_id).update(
            salida_en=self.party().creada_en, motivo_salida='desconexion')

        self.assertEqual(self.expulsar(miembro).status_code, 204)

        self.assertIsNotNone(self.party().finalizada_en)
        self.assertEqual(self.tipos_de_eventos()[-1][0], 'party.finalizada')

    def test_expulsar_de_nuevo_no_cambia_nada(self):
        miembro = self.agregar()
        self.expulsar(miembro)
        version = self.party().version

        self.assertEqual(self.expulsar(miembro).status_code, 204)
        self.assertEqual(self.party().version, version)


class RehabilitarTests(PruebasExpulsion):

    def test_rehabilitar_permite_volver_como_oyente_sin_conectarlo(self):
        miembro = self.agregar()
        MiembroParty.objects.filter(usuario_id=miembro).update(puede_modificar_cola=True)
        self.expulsar(miembro)
        version = self.party().version

        self.assertEqual(self.rehabilitar(miembro).status_code, 204)

        self.assertEqual(self.miembro(miembro).estado, 'habilitado')
        self.assertIsNotNone(self.participacion(miembro).salida_en)
        self.assertEqual(self.tipos_de_eventos()[-1], ('miembro.rehabilitado', version + 1))
        respuesta = self.unirse(miembro)
        self.assertEqual(respuesta.status_code, 200)
        propio = next(m for m in respuesta.json()['miembros'] if m['usuario_id'] == str(miembro))
        self.assertEqual((propio['puede_aportar'], propio['puede_modificar_cola']), (False, False))

    def test_rehabilitar_a_quien_no_fue_expulsado_no_cambia_nada(self):
        miembro = self.agregar()
        version = self.party().version

        self.assertEqual(self.rehabilitar(miembro).status_code, 204)
        self.assertEqual(self.party().version, version)


class ValidacionTests(PruebasExpulsion):

    def test_solo_el_anfitrion(self):
        miembro, otro = self.agregar(), self.agregar()
        for accion in ('expulsar', 'rehabilitar'):
            self.verificar_error(self.administrar(accion, otro, usuario_id=miembro),
                                 403, 'NO_ES_ANFITRION')
        self.assertEqual(self.miembro(otro).estado, 'habilitado')

    def test_el_anfitrion_no_puede_expulsarse(self):
        self.verificar_error(self.expulsar(self.anfitrion_id), 400, 'DATOS_INVALIDOS')

    def test_version_obsoleta(self):
        miembro = self.agregar()
        respuesta = self.expulsar(miembro, version=self.party().version - 1)
        self.verificar_error(respuesta, 409, 'VERSION_OBSOLETA')
        self.assertEqual(respuesta.json()['detalles']['version_actual'], self.party().version)
        self.assertEqual(self.miembro(miembro).estado, 'habilitado')

    def test_quien_no_es_miembro(self):
        self.verificar_error(self.expulsar(uuid.uuid4()), 404, 'NO_ENCONTRADO')

    def test_party_finalizada(self):
        miembro = self.agregar()
        version = self.party().version
        self.finalizar(self.anfitrion_id)
        self.verificar_error(self.expulsar(miembro, version=version), 410, 'PARTY_FINALIZADA')

    def test_exige_version_y_clave(self):
        miembro = self.agregar()
        self.verificar_error(self.expulsar(miembro, cuerpo={}), 400, 'DATOS_INVALIDOS')
        self.verificar_error(self.expulsar(miembro, clave='sin_clave'), 400, 'DATOS_INVALIDOS')

    def test_repetir_con_la_misma_clave_no_repite_efectos(self):
        miembro = self.agregar()
        clave = uuid.uuid4()
        version = self.party().version
        self.expulsar(miembro, clave=clave, version=version)
        version_tras = self.party().version

        self.assertEqual(self.expulsar(miembro, clave=clave, version=version).status_code, 204)
        self.assertEqual(self.party().version, version_tras)
        self.verificar_error(self.rehabilitar(miembro, clave=clave, version=version_tras),
                             409, 'IDEMPOTENCIA_CONFLICTO')


class WebSocketExpulsionTests(PruebasWebSocketParty):

    async def test_el_expulsado_recibe_su_expulsion_y_el_servidor_cierra_con_4003(self):
        expulsado, cliente = await self.conectar_miembro()
        _, otro = await self.conectar_miembro()
        version = await database_sync_to_async(
            lambda: Party.objects.get(id=self.party_id).version)()

        await database_sync_to_async(expulsar_miembro)(
            SimpleNamespace(id=self.anfitrion_id), self.party_id, expulsado, version, uuid.uuid4())

        evento = await cliente.receive_json_from(timeout=1)
        self.assertEqual((evento['tipo'], evento['datos']['usuario_id']),
                         ('miembro.expulsado', str(expulsado)))
        self.assertEqual(await self.cierre(cliente), 4003)
        tipos = [(await otro.receive_json_from(timeout=1))['tipo'] for _ in range(2)]
        self.assertEqual(tipos, ['miembro.expulsado', 'miembro.salida'])
        self.assertTrue(await otro.receive_nothing(timeout=0.2))
