import threading
import uuid
from datetime import timedelta
from unittest.mock import patch

from django.db import connection
from django.test import TransactionTestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.parties.models import (EventoSalida, InvitacionParty, MiembroParty, ParticipacionParty,
                                 Party)
from .utilidades import CLAVE_PUBLICA, PruebasBase, hacer_token, vaciar_tablas_party


class PruebasUnirse(PruebasBase):
    URL_UNIRSE = '/api/v1/party/parties/unirse'

    def setUp(self):
        super().setUp()
        self.anfitrion_id = uuid.uuid4()
        estado = self.crear(self.anfitrion_id).json()
        self.party_id = uuid.UUID(estado['id'])
        self.codigo = estado['codigo']

    def unirse(self, usuario_id=None, codigo=None, clave=None, cuerpo=None):
        usuario_id = usuario_id or uuid.uuid4()
        cuerpo = {'codigo': codigo or self.codigo} if cuerpo is None else cuerpo
        return self.cliente.post(
            self.URL_UNIRSE, cuerpo, format='json',
            HTTP_AUTHORIZATION=f'Bearer {hacer_token(usuario_id, nombre_usuario="axel")}',
            HTTP_IDEMPOTENCY_KEY=str(clave or uuid.uuid4()),
        )

    def contar_conectados(self):
        abiertas = ParticipacionParty.objects.filter(party_id=self.party_id, salida_en__isnull=True)
        return abiertas.count()

    def verificar_error(self, respuesta, estado, codigo, mensaje=None):
        obtenido = (respuesta.status_code, respuesta.json()['codigo'])
        self.assertEqual(obtenido, (estado, codigo), mensaje)

    def salir(self, usuario_id, motivo, hace):
        salida = timezone.now() - hace
        ParticipacionParty.objects.filter(usuario_id=usuario_id, salida_en__isnull=True).update(
            entrada_en=salida - timedelta(minutes=1), salida_en=salida, motivo_salida=motivo)


class UnirseTests(PruebasUnirse):
    def test_entra_como_oyente_y_ve_la_party(self):
        usuario_id = uuid.uuid4()
        respuesta = self.unirse(usuario_id)

        self.assertEqual(respuesta.status_code, 200)
        estado = respuesta.json()
        self.assertEqual(estado['id'], str(self.party_id))
        self.assertIsNone(estado['codigo'])
        yo = next(m for m in estado['miembros'] if m['usuario_id'] == str(usuario_id))
        self.assertEqual((yo['puede_aportar'], yo['puede_modificar_cola']), (False, False))
        self.assertEqual(yo['nombre_usuario'], 'axel')
        self.assertTrue(yo['conectado'])
        self.assertEqual(estado['version'], 2)

    def test_deja_el_evento_de_ingreso_con_la_nueva_version(self):
        usuario_id = uuid.uuid4()
        self.unirse(usuario_id)
        evento = EventoSalida.objects.get(agregado_id=self.party_id, tipo='miembro.ingreso')
        self.assertEqual(evento.version, 2)
        self.assertEqual(evento.datos['usuario_id'], str(usuario_id))

    def test_avisa_por_websocket_al_confirmar(self):
        with patch('apps.parties.servicios.publicar') as publicar, \
                self.captureOnCommitCallbacks(execute=True):
            self.unirse()
        party_id, tipo, datos, version = publicar.call_args.args
        self.assertEqual((party_id, tipo, version), (str(self.party_id), 'miembro.ingreso', 2))

    def test_si_redis_falla_el_ingreso_sigue_valiendo(self):
        with patch('apps.parties.servicios.publicar', side_effect=ConnectionError), \
                self.assertLogs('apps.parties.servicios', 'ERROR'), \
                self.captureOnCommitCallbacks(execute=True):
            respuesta = self.unirse()
        self.assertEqual(respuesta.status_code, 200)

    def test_acepta_minusculas_y_espacios(self):
        self.assertEqual(self.unirse(codigo=f'  {self.codigo.lower()} ').status_code, 200)

    def test_codigo_que_no_existe_o_mal_escrito(self):
        for codigo in ('ZZZZZZ' if self.codigo != 'ZZZZZZ' else 'YYYYYY', 'ABC', 'ÑÑÑÑÑÑ'):
            respuesta = self.unirse(codigo=codigo)
            self.verificar_error(respuesta, 404, 'CODIGO_INVALIDO', codigo)

    def test_sin_codigo_es_datos_invalidos(self):
        for cuerpo in ({}, {'codigo': 123}, []):
            self.assertEqual(self.unirse(cuerpo=cuerpo).json()['codigo'], 'DATOS_INVALIDOS', cuerpo)

    def test_codigo_revocado(self):
        InvitacionParty.objects.filter(party_id=self.party_id).update(revocada_en=timezone.now())
        self.assertEqual(self.unirse().json()['codigo'], 'CODIGO_INVALIDO')

    def test_codigo_vencido(self):
        vencio = timezone.now() - timedelta(seconds=1)
        InvitacionParty.objects.filter(party_id=self.party_id).update(
            creada_en=vencio - timedelta(days=1), expira_en=vencio)
        respuesta = self.unirse()
        self.verificar_error(respuesta, 410, 'CODIGO_EXPIRADO')

    def test_party_finalizada(self):
        Party.objects.filter(id=self.party_id).update(finalizada_en=timezone.now())
        respuesta = self.unirse()
        self.verificar_error(respuesta, 410, 'PARTY_FINALIZADA')

    def test_un_expulsado_no_puede_volver(self):
        usuario_id = uuid.uuid4()
        self.unirse(usuario_id)
        self.salir(usuario_id, 'expulsion', timedelta(seconds=5))
        MiembroParty.objects.filter(usuario_id=usuario_id).update(estado='expulsado')

        respuesta = self.unirse(usuario_id)
        self.verificar_error(respuesta, 403, 'USUARIO_EXPULSADO')

    def test_no_puede_estar_en_dos_parties(self):
        usuario_id = uuid.uuid4()
        self.crear(usuario_id)
        respuesta = self.unirse(usuario_id)
        self.verificar_error(respuesta, 409, 'YA_EN_OTRA_PARTY')

    def test_volver_a_unirse_estando_dentro_no_duplica(self):
        usuario_id = uuid.uuid4()
        self.unirse(usuario_id)
        respuesta = self.unirse(usuario_id)

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(ParticipacionParty.objects.filter(usuario_id=usuario_id).count(), 1)
        self.assertEqual(respuesta.json()['version'], 2)

    def test_con_20_conectados_la_party_esta_llena(self):
        for _ in range(19):
            self.assertEqual(self.unirse().status_code, 200)
        respuesta = self.unirse()

        self.verificar_error(respuesta, 409, 'PARTY_LLENA')
        self.assertEqual(self.contar_conectados(), 20)

    def test_si_alguien_sale_se_libera_el_lugar(self):
        primero = uuid.uuid4()
        self.unirse(primero)
        for _ in range(18):
            self.unirse()
        self.salir(primero, 'voluntaria', timedelta(seconds=1))
        self.assertEqual(self.unirse().status_code, 200)


class ReconexionTests(PruebasUnirse):
    def entrar_con_permisos(self):
        usuario_id = uuid.uuid4()
        self.unirse(usuario_id)
        MiembroParty.objects.filter(usuario_id=usuario_id).update(puede_aportar=True,
                                                                  puede_modificar_cola=True)
        return usuario_id

    def obtener_permisos(self, usuario_id):
        miembro = MiembroParty.objects.get(usuario_id=usuario_id)
        return miembro.puede_aportar, miembro.puede_modificar_cola

    def test_reconectar_antes_de_60_s_conserva_los_permisos(self):
        usuario_id = self.entrar_con_permisos()
        self.salir(usuario_id, 'desconexion', timedelta(seconds=30))
        self.assertEqual(self.unirse(usuario_id).status_code, 200)
        self.assertEqual(self.obtener_permisos(usuario_id), (True, True))

    def test_reconectar_despues_de_60_s_entra_como_oyente(self):
        usuario_id = self.entrar_con_permisos()
        self.salir(usuario_id, 'desconexion', timedelta(seconds=61))
        self.unirse(usuario_id)
        self.assertEqual(self.obtener_permisos(usuario_id), (False, False))

    def test_volver_tras_salir_por_su_cuenta_entra_como_oyente(self):
        usuario_id = self.entrar_con_permisos()
        self.salir(usuario_id, 'voluntaria', timedelta(seconds=5))
        self.unirse(usuario_id)
        self.assertEqual(self.obtener_permisos(usuario_id), (False, False))


class IdempotenciaUnirseTests(PruebasUnirse):
    def test_repetir_la_clave_devuelve_lo_mismo(self):
        usuario_id, clave = uuid.uuid4(), uuid.uuid4()
        primera = self.unirse(usuario_id, clave=clave)
        segunda = self.unirse(usuario_id, clave=clave)

        self.assertEqual(segunda.status_code, 200)
        self.assertEqual(segunda.json()['id'], primera.json()['id'])
        self.assertEqual(EventoSalida.objects.filter(tipo='miembro.ingreso').count(), 1)

    def test_la_misma_clave_con_otro_codigo_es_conflicto(self):
        usuario_id, clave = uuid.uuid4(), uuid.uuid4()
        self.unirse(usuario_id, clave=clave)
        otro = 'ZZZZZZ' if self.codigo != 'ZZZZZZ' else 'YYYYYY'
        respuesta = self.unirse(usuario_id, codigo=otro, clave=clave)
        self.verificar_error(respuesta, 409, 'IDEMPOTENCIA_CONFLICTO')


@override_settings(JWT_CLAVE_PUBLICA=CLAVE_PUBLICA)
class IngresosSimultaneosTests(TransactionTestCase):
    """Plan T-33: con ingresos simultáneos nunca hay más de 20 conectados."""

    def tearDown(self):
        vaciar_tablas_party()

    def test_21_ingresos_a_la_vez_no_pasan_de_20_conectados(self):
        anfitrion_id = uuid.uuid4()
        codigo = APIClient().post(
            '/api/v1/party/parties', {'nombre': 'Viernes'}, format='json',
            HTTP_AUTHORIZATION=f'Bearer {hacer_token(anfitrion_id)}',
            HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()),
        ).json()['codigo']

        salida = threading.Barrier(21)
        resultados = []

        def entrar():
            try:
                cliente = APIClient()
                salida.wait()
                respuesta = cliente.post(
                    '/api/v1/party/parties/unirse', {'codigo': codigo}, format='json',
                    HTTP_AUTHORIZATION=f'Bearer {hacer_token()}',
                    HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()),
                )
                es_exito = respuesta.status_code == 200
                resultados.append(200 if es_exito else respuesta.json().get('codigo'))
            finally:
                connection.close()

        hilos = [threading.Thread(target=entrar) for _ in range(21)]
        for hilo in hilos:
            hilo.start()
        for hilo in hilos:
            hilo.join()

        self.assertEqual(resultados.count(200), 19, 'el anfitrión ya ocupa uno de los 20 lugares')
        self.assertEqual(resultados.count('PARTY_LLENA'), 2)
        self.assertEqual(ParticipacionParty.objects.filter(salida_en__isnull=True).count(), 20)
        self.assertEqual(Party.objects.get().version, 20)
