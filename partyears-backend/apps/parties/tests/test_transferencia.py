import uuid
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest.mock import patch

from django.db import connection
from django.test import TransactionTestCase, override_settings

from apps.parties.errores import ErrorApi
from apps.parties.models import AnfitrionParty, MiembroParty, Party
from apps.parties.servicios import transferir_anfitrion
from .test_expulsion import PruebasExpulsion
from .utilidades import (CLAVE_PUBLICA, agregar_miembro, crear_party_en_bd, hacer_token,
                         vaciar_tablas_party)


class PruebasTransferencia(PruebasExpulsion):

    def transferir(self, destinatario_id, usuario_id=None, version=None, clave=None,
                   cuerpo=None):
        cabeceras = {'HTTP_AUTHORIZATION': f'Bearer {hacer_token(usuario_id or self.anfitrion_id)}'}
        if clave != 'sin_clave':
            cabeceras['HTTP_IDEMPOTENCY_KEY'] = str(clave or uuid.uuid4())
        if cuerpo is None:
            cuerpo = {'usuario_id': str(destinatario_id),
                      'version_esperada': self.party().version if version is None else version}
        return self.cliente.post(f'{self.URL}/{self.party_id}/anfitrion', cuerpo, format='json',
                                 **cabeceras)


class TransferirTests(PruebasTransferencia):

    def test_el_cargo_pasa_al_destinatario_con_todos_los_permisos(self):
        destinatario = self.agregar()
        version = self.party().version

        self.assertEqual(self.transferir(destinatario).status_code, 204)

        self.assertEqual(self.anfitrion(), destinatario)
        nuevo, anterior = self.miembro(destinatario), self.miembro(self.anfitrion_id)
        self.assertEqual((nuevo.puede_aportar, nuevo.puede_modificar_cola), (True, True))
        self.assertEqual((anterior.puede_aportar, anterior.puede_modificar_cola), (True, True))
        self.assertEqual(self.tipos_de_eventos()[-2:],
                         [('anfitrion.cambio', version + 1), ('miembro.permisos', version + 2)])

    def test_avisa_el_cambio_manual(self):
        destinatario = self.agregar()
        with patch('apps.parties.servicios.publicar') as publicar, \
                self.captureOnCommitCallbacks(execute=True):
            self.transferir(destinatario)
        _, tipo, datos, _ = publicar.call_args_list[0].args
        self.assertEqual((tipo, datos), ('anfitrion.cambio', {
            'anterior_id': str(self.anfitrion_id), 'nuevo_id': str(destinatario),
            'motivo': 'manual'}))

    def test_el_anterior_pierde_las_facultades_del_cargo(self):
        destinatario = self.agregar()
        self.transferir(destinatario)

        self.verificar_error(self.transferir(self.anfitrion_id, usuario_id=self.anfitrion_id),
                             403, 'NO_ES_ANFITRION')
        self.verificar_error(self.finalizar(self.anfitrion_id), 403, 'NO_ES_ANFITRION')
        self.assertEqual(self.finalizar(destinatario).status_code, 204)

    def test_el_destinatario_debe_estar_conectado_y_habilitado(self):
        desconectado = self.agregar(esta_conectado=False)
        expulsado = self.agregar(estado='expulsado')
        for destinatario in (desconectado, expulsado):
            self.verificar_error(self.transferir(destinatario), 409, 'DESTINATARIO_NO_ELEGIBLE')
        self.assertEqual(self.anfitrion(), self.anfitrion_id)

    def test_solo_el_anfitrion_transfiere(self):
        miembro, otro = self.agregar(), self.agregar()
        self.verificar_error(self.transferir(otro, usuario_id=miembro), 403, 'NO_ES_ANFITRION')

    def test_rechaza_datos_invalidos(self):
        self.verificar_error(self.transferir(self.anfitrion_id), 400, 'DATOS_INVALIDOS')
        self.verificar_error(self.transferir(None, cuerpo={'version_esperada': 1}),
                             400, 'DATOS_INVALIDOS')
        self.verificar_error(self.transferir(None, cuerpo={'usuario_id': str(uuid.uuid4())}),
                             400, 'DATOS_INVALIDOS')
        self.verificar_error(self.transferir(uuid.uuid4()), 404, 'NO_ENCONTRADO')

    def test_version_obsoleta(self):
        destinatario = self.agregar()
        respuesta = self.transferir(destinatario, version=self.party().version - 1)
        self.verificar_error(respuesta, 409, 'VERSION_OBSOLETA')
        self.assertEqual(self.anfitrion(), self.anfitrion_id)

    def test_repetir_con_la_misma_clave_no_repite_efectos(self):
        destinatario = self.agregar()
        clave, version = uuid.uuid4(), self.party().version
        self.transferir(destinatario, clave=clave, version=version)
        version_tras = self.party().version

        self.assertEqual(self.transferir(destinatario, clave=clave, version=version).status_code,
                         204)
        self.assertEqual(self.party().version, version_tras)


class TransferenciasSimultaneasTests(TransactionTestCase):
    """CU-24 FA-01: dos transferencias a la vez dejan un solo anfitrión."""

    def tearDown(self):
        vaciar_tablas_party()

    @override_settings(JWT_CLAVE_PUBLICA=CLAVE_PUBLICA)
    def test_solo_una_de_dos_transferencias_simultaneas_se_aplica(self):
        anfitrion_id, uno, otro = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        party_id = crear_party_en_bd(anfitrion_id)
        agregar_miembro(party_id, uno)
        agregar_miembro(party_id, otro)
        version = Party.objects.get(id=party_id).version

        def transferir(destinatario_id):
            try:
                usuario = SimpleNamespace(id=anfitrion_id)
                return transferir_anfitrion(usuario, party_id, destinatario_id, version,
                                            uuid.uuid4())
            except ErrorApi as error:
                return error.codigo
            finally:
                connection.close()

        with patch('apps.parties.servicios.publicar'), ThreadPoolExecutor(2) as hilos:
            resultados = list(hilos.map(transferir, (uno, otro)))

        # The second one waits for the lock and finds the caller is no longer the host.
        self.assertEqual(sorted(map(str, resultados)), ['(None, 204)', 'NO_ES_ANFITRION'])
        ganador = AnfitrionParty.objects.get(party_id=party_id).usuario_id
        self.assertEqual(ganador, (uno, otro)[resultados.index((None, 204))])
        self.assertEqual(MiembroParty.objects.get(party_id=party_id, usuario_id=ganador)
                         .puede_modificar_cola, True)
