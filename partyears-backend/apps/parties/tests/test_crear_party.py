import re
import time
import uuid
from datetime import timedelta
from unittest.mock import patch
import jwt
from django.db import IntegrityError, transaction
from django.utils import timezone
from apps.mensajeria.publicador import TIPO_OPERACION
from apps.parties.codigos import generar_codigo
from apps.parties.models import (AnfitrionParty, EventoSalida, InvitacionParty, MiembroParty, OperacionConfirmada, ParticipacionParty, Party)
from .utilidades import CLAVE_PRIVADA, OTRA_CLAVE_PRIVADA, PruebasBase, hacer_token

CODIGO_VALIDO = re.compile(r'^[A-Z0-9]{6}$')

class CrearPartyTests(PruebasBase):
    def test_crea_la_party_con_el_creador_como_anfitrion(self):
        usuario_id = uuid.uuid4()
        respuesta = self.crear(usuario_id)

        self.assertEqual(respuesta.status_code, 201)
        estado = respuesta.json()
        self.assertRegex(estado['codigo'], CODIGO_VALIDO)
        self.assertEqual(estado['nombre'], 'Viernes')
        self.assertEqual(estado['anfitrion_id'], str(usuario_id))
        self.assertEqual(estado['version'], 1)
        self.assertIsNone(estado['finalizada_en'])
        self.assertTrue(estado['creada_en'].endswith('Z'))

        self.assertEqual(len(estado['miembros']), 1)
        miembro = estado['miembros'][0]
        self.assertEqual(miembro['usuario_id'], str(usuario_id))
        self.assertEqual(miembro['nombre_usuario'], 'mariana')
        self.assertTrue(miembro['puede_aportar'])
        self.assertTrue(miembro['puede_modificar_cola'])
        self.assertEqual(miembro['estado'], 'habilitado')
        self.assertTrue(miembro['conectado'])
        self.assertIsInstance(miembro['orden_ingreso'], int)

    def test_guarda_todo_en_una_transaccion(self):
        usuario_id = uuid.uuid4()
        clave = uuid.uuid4()
        estado = self.crear(usuario_id, clave=clave).json()

        party = Party.objects.get(id=estado['id'])
        self.assertEqual(party.creada_por, usuario_id)
        self.assertEqual(party.capacidad, 20)
        self.assertEqual(MiembroParty.objects.filter(party=party).count(), 1)
        self.assertEqual(AnfitrionParty.objects.get(party=party).usuario_id, usuario_id)
        self.assertEqual(ParticipacionParty.objects.filter(party=party, salida_en__isnull=True).count(), 1)

        invitacion = InvitacionParty.objects.get(party=party)
        self.assertEqual(invitacion.codigo, estado['codigo'])
        self.assertEqual(invitacion.creada_por, usuario_id)
        self.assertIsNone(invitacion.revocada_en)
        self.assertEqual(invitacion.expira_en - invitacion.creada_en, timedelta(hours=24))

        recibo = OperacionConfirmada.objects.get(actor_id=usuario_id, clave=clave)
        self.assertEqual(recibo.codigo_respuesta, 201)
        self.assertEqual(recibo.resultado['party_id'], estado['id'])

        evento = EventoSalida.objects.get(agregado_id=party.id, tipo='party.creada')
        self.assertEqual(evento.tipo, 'party.creada')
        self.assertIsNone(evento.publicado_en)

    def test_el_codigo_copiado_es_el_mostrado_y_la_consulta_lo_repite(self):
        usuario_id = uuid.uuid4()
        creada = self.crear(usuario_id).json()
        actual = self.consultar_actual(usuario_id)

        self.assertEqual(actual.status_code, 200)
        self.assertEqual(actual.json()['codigo'], creada['codigo'])
        self.assertEqual(actual.json()['id'], creada['id'])

    def test_los_codigos_generados_cumplen_el_formato(self):
        for _ in range(200):
            self.assertRegex(generar_codigo(), CODIGO_VALIDO)

    def test_dos_parties_nunca_comparten_codigo(self):
        primera = self.crear().json()
        party = Party.objects.get(id=primera['id'])
        invitacion_anterior = InvitacionParty.objects.get(party=party)

        with self.assertRaises(IntegrityError), transaction.atomic():
            InvitacionParty.objects.create(party=party, codigo=primera['codigo'], creada_por=party.creada_por, expira_en=timezone.now() + timedelta(hours=1))
        self.assertEqual(InvitacionParty.objects.filter(codigo=invitacion_anterior.codigo).count(), 1)

    def test_si_el_codigo_choca_genera_otro(self):
        primera = self.crear().json()

        with patch('apps.parties.servicios.generar_codigo', side_effect=[primera['codigo'], 'ZZZZZZ']):
            segunda = self.crear()

        self.assertEqual(segunda.status_code, 201)
        self.assertEqual(segunda.json()['codigo'], 'ZZZZZZ')
        self.assertNotEqual(segunda.json()['id'], primera['id'])

    def test_si_no_logra_un_codigo_unico_no_crea_la_party(self):
        primera = self.crear().json()

        with patch('apps.parties.servicios.generar_codigo', return_value=primera['codigo']):
            respuesta = self.crear()

        self.assertEqual(respuesta.status_code, 503)
        self.assertEqual(respuesta.json()['codigo'], 'SERVICIO_NO_DISPONIBLE')
        self.assertEqual(Party.objects.count(), 1)
        self.assertEqual(OperacionConfirmada.objects.count(), 1)


class ValidacionTests(PruebasBase):
    def test_rechaza_nombres_invalidos(self):
        for cuerpo in ({}, {'nombre': ''}, {'nombre': '   '}, {'nombre': 5}, {'nombre': 'a' * 101}, [1, 2]):
            with self.subTest(cuerpo=cuerpo):
                respuesta = self.crear(cuerpo=cuerpo)
                self.assertEqual(respuesta.status_code, 400)
                self.assertEqual(respuesta.json()['codigo'], 'DATOS_INVALIDOS')

        self.assertEqual(Party.objects.count(), 0)

    def test_el_error_de_nombre_indica_el_campo(self):
        cuerpo = self.crear(cuerpo={'nombre': ' '}).json()
        self.assertEqual(cuerpo['detalles'], {'nombre': ['Este campo es obligatorio.']})

    def test_acepta_nombre_de_100_caracteres_y_lo_recorta(self):
        self.assertEqual(self.crear(cuerpo={'nombre': 'a' * 100}).status_code, 201)
        self.assertEqual(self.crear(cuerpo={'nombre': '  Fiesta  '}).json()['nombre'], 'Fiesta')

    def test_exige_idempotency_key_valida(self):
        self.assertEqual(self.crear(clave='sin_clave').status_code, 400)
        self.assertEqual(self.crear(clave='no-es-uuid').status_code, 400)
        self.assertEqual(self.crear(clave='sin_clave').json()['codigo'], 'DATOS_INVALIDOS')

    def test_la_cancion_inicial_debe_ser_uuid_o_null(self):
        self.assertEqual(self.crear(cuerpo={'nombre': 'A', 'recurso_audio_id_inicial': 'x'}).status_code, 400)
        self.assertEqual(self.crear(cuerpo={'nombre': 'B', 'recurso_audio_id_inicial': None}).status_code, 201)
        self.assertEqual(self.crear(cuerpo={'nombre': 'C', 'recurso_audio_id_inicial': str(uuid.uuid4())}).status_code, 201)

    def test_un_json_mal_formado_da_datos_invalidos(self):
        respuesta = self.cliente.post(self.URL, '{no es json', content_type='application/json', HTTP_AUTHORIZATION=f'Bearer {hacer_token()}', HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))
        self.assertEqual(respuesta.status_code, 400)
        self.assertEqual(respuesta.json()['codigo'], 'DATOS_INVALIDOS')


class YaEnOtraPartyTests(PruebasBase):
    def test_un_usuario_no_puede_tener_dos_parties_activas(self):
        usuario_id = uuid.uuid4()
        self.assertEqual(self.crear(usuario_id).status_code, 201)

        segunda = self.crear(usuario_id)
        self.assertEqual(segunda.status_code, 409)
        self.assertEqual(segunda.json()['codigo'], 'YA_EN_OTRA_PARTY')
        self.assertEqual(Party.objects.count(), 1)

    def test_dos_usuarios_distintos_si_pueden_crear_cada_uno_la_suya(self):
        self.assertEqual(self.crear().status_code, 201)
        self.assertEqual(self.crear().status_code, 201)
        self.assertEqual(Party.objects.count(), 2)

    def test_puede_crear_otra_cuando_la_anterior_ya_termino(self):
        usuario_id = uuid.uuid4()
        primera = self.crear(usuario_id).json()
        ahora = timezone.now()
        ParticipacionParty.objects.filter(party_id=primera['id']).update(salida_en=ahora, motivo_salida='voluntaria')
        Party.objects.filter(id=primera['id']).update(finalizada_en=ahora)

        self.assertEqual(self.crear(usuario_id).status_code, 201)


class IdempotenciaTests(PruebasBase):
    def test_repetir_la_misma_clave_devuelve_lo_mismo_sin_duplicar(self):
        usuario_id = uuid.uuid4()
        clave = uuid.uuid4()
        primera = self.crear(usuario_id, clave=clave)
        repetida = self.crear(usuario_id, clave=clave)

        self.assertEqual(primera.status_code, 201)
        self.assertEqual(repetida.status_code, 201)
        self.assertEqual(repetida.json(), primera.json())
        self.assertEqual(Party.objects.count(), 1)
        self.assertEqual(InvitacionParty.objects.count(), 1)
        self.assertEqual(EventoSalida.objects.exclude(tipo=TIPO_OPERACION).count(), 1)

    def test_el_reintento_funciona_aunque_el_usuario_ya_este_en_la_party(self):
        usuario_id = uuid.uuid4()
        clave = uuid.uuid4()
        self.crear(usuario_id, clave=clave)

        self.assertEqual(self.crear(usuario_id, clave=clave).status_code, 201)

    def test_la_misma_clave_con_otro_contenido_es_conflicto(self):
        usuario_id = uuid.uuid4()
        clave = uuid.uuid4()
        self.crear(usuario_id, cuerpo={'nombre': 'Viernes'}, clave=clave)
        conflicto = self.crear(usuario_id, cuerpo={'nombre': 'Sabado'}, clave=clave)

        self.assertEqual(conflicto.status_code, 409)
        self.assertEqual(conflicto.json()['codigo'], 'IDEMPOTENCIA_CONFLICTO')
        self.assertEqual(Party.objects.count(), 1)

    def test_la_misma_clave_de_otro_usuario_no_choca(self):
        clave = uuid.uuid4()
        self.assertEqual(self.crear(clave=clave).status_code, 201)
        self.assertEqual(self.crear(clave=clave).status_code, 201)
        self.assertEqual(Party.objects.count(), 2)


class PartyActualTests(PruebasBase):
    def test_sin_party_responde_204(self):
        respuesta = self.consultar_actual(uuid.uuid4())
        self.assertEqual(respuesta.status_code, 204)

    def test_un_miembro_que_no_es_anfitrion_no_recibe_el_codigo(self):
        creada = self.crear().json()
        party = Party.objects.get(id=creada['id'])
        otro = uuid.uuid4()
        MiembroParty.objects.create(party=party, usuario_id=otro)
        ParticipacionParty.objects.create(party=party, usuario_id=otro)

        respuesta = self.consultar_actual(otro, nombre_usuario='darlington')
        self.assertEqual(respuesta.status_code, 200)
        estado = respuesta.json()
        self.assertIsNone(estado['codigo'])
        self.assertEqual(len(estado['miembros']), 2)
        nombres = {m['usuario_id']: m['nombre_usuario'] for m in estado['miembros']}
        self.assertEqual(nombres[str(otro)], 'darlington')
        self.assertIsNone(nombres[creada['anfitrion_id']])

    def test_una_party_finalizada_ya_no_es_la_actual(self):
        usuario_id = uuid.uuid4()
        creada = self.crear(usuario_id).json()
        Party.objects.filter(id=creada['id']).update(finalizada_en=timezone.now())

        self.assertEqual(self.consultar_actual(usuario_id).status_code, 204)

    def test_el_anfitrion_que_consulta_renueva_la_vigencia_del_codigo(self):
        usuario_id = uuid.uuid4()
        creada = self.crear(usuario_id).json()
        InvitacionParty.objects.filter(party_id=creada['id']).update(expira_en=timezone.now() + timedelta(hours=1))

        self.consultar_actual(usuario_id)

        invitacion = InvitacionParty.objects.get(party_id=creada['id'])
        self.assertGreater(invitacion.expira_en, timezone.now() + timedelta(hours=23))


class AutenticacionTests(PruebasBase):
    def verificar_401(self, respuesta):
        self.assertEqual(respuesta.status_code, 401)
        self.assertEqual(respuesta.json()['codigo'], 'TOKEN_INVALIDO')
        self.assertEqual(Party.objects.count(), 0)

    def test_sin_token(self):
        respuesta = self.cliente.post(self.URL, {'nombre': 'A'}, format='json', HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))
        self.verificar_401(respuesta)

    def test_token_firmado_con_otra_clave(self):
        self.verificar_401(self.crear(token=hacer_token(clave=OTRA_CLAVE_PRIVADA)))

    def test_token_vencido(self):
        self.verificar_401(self.crear(token=hacer_token(vence_en=-10)))

    def test_token_sin_sub_uuid(self):
        ahora = int(time.time())
        token = jwt.encode({'sub': 'no-es-uuid', 'exp': ahora + 300}, CLAVE_PRIVADA, algorithm='RS256')
        self.verificar_401(self.crear(token=token))

    def test_token_sin_algoritmo(self):
        ahora = int(time.time())
        token = jwt.encode({'sub': str(uuid.uuid4()), 'exp': ahora + 300}, key=None, algorithm='none')
        self.verificar_401(self.crear(token=token))

    def test_cabecera_con_formato_incorrecto(self):
        respuesta = self.cliente.post(self.URL, {'nombre': 'A'}, format='json', HTTP_AUTHORIZATION=f'Token {hacer_token()}', HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))
        self.verificar_401(respuesta)

    def test_consultar_la_party_actual_tambien_exige_token(self):
        self.assertEqual(self.cliente.get(self.URL + '/actual').status_code, 401)