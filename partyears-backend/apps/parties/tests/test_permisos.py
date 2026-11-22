import uuid
from unittest.mock import patch

from django.utils import timezone

from apps.parties.models import EventoSalida, MiembroParty, ParticipacionParty, Party
from .utilidades import PruebasBase, agregar_miembro, hacer_token


class PermisosTests(PruebasBase):

    def setUp(self):
        super().setUp()
        self.anfitrion_id = uuid.uuid4()
        estado = self.crear(self.anfitrion_id).json()
        self.party_id = estado['id']
        self.version = estado['version']
        self.miembro_id = uuid.uuid4()
        agregar_miembro(self.party_id, self.miembro_id)

    def cambiar(self, puede_aportar=True, puede_modificar_cola=False, version=None,
                usuario_id=None, miembro_id=None, clave=None, cuerpo=None):
        cuerpo = cuerpo if cuerpo is not None else {
            'puede_aportar': puede_aportar, 'puede_modificar_cola': puede_modificar_cola,
            'version_esperada': self.version if version is None else version}
        url = f'{self.URL}/{self.party_id}/miembros/{miembro_id or self.miembro_id}/permisos'
        token = hacer_token(usuario_id or self.anfitrion_id)
        return self.cliente.put(url, cuerpo, format='json', HTTP_AUTHORIZATION=f'Bearer {token}',
                                HTTP_IDEMPOTENCY_KEY=str(clave or uuid.uuid4()))

    def permisos(self, usuario_id=None):
        miembro = MiembroParty.objects.get(party_id=self.party_id,
                                           usuario_id=usuario_id or self.miembro_id)
        return miembro.puede_aportar, miembro.puede_modificar_cola

    def verificar_error(self, respuesta, estado, codigo):
        self.assertEqual((respuesta.status_code, respuesta.json()['codigo']), (estado, codigo))

    def test_las_cuatro_combinaciones(self):
        for combinacion in ((True, False), (False, True), (True, True), (False, False)):
            respuesta = self.cambiar(*combinacion)
            self.assertEqual(respuesta.status_code, 200)
            self.assertEqual(self.permisos(), combinacion)
            self.version = respuesta.json()['version']

    def test_responde_el_miembro_y_la_nueva_version(self):
        cuerpo = self.cambiar(True, True).json()
        self.assertEqual(cuerpo['version'], self.version + 1)
        miembro = cuerpo['miembro']
        self.assertEqual((miembro['usuario_id'], miembro['puede_aportar'],
                          miembro['puede_modificar_cola'], miembro['conectado']),
                         (str(self.miembro_id), True, True, True))

    def test_deja_el_evento_y_avisa_tras_confirmar(self):
        with patch('apps.parties.servicios.publicar') as publicar, \
                self.captureOnCommitCallbacks(execute=True):
            self.cambiar(True, False)
        evento = EventoSalida.objects.get(tipo='miembro.permisos')
        datos = {'usuario_id': str(self.miembro_id), 'puede_aportar': True,
                 'puede_modificar_cola': False}
        self.assertEqual((evento.datos, evento.version), (datos, self.version + 1))
        self.assertEqual(publicar.call_args.args[1:], ('miembro.permisos', datos, self.version + 1))

    def test_solo_el_anfitrion(self):
        self.verificar_error(self.cambiar(usuario_id=self.miembro_id), 403, 'NO_ES_ANFITRION')
        self.assertEqual(self.permisos(), (False, False))

    def test_no_se_cambian_los_del_anfitrion(self):
        self.verificar_error(self.cambiar(False, False, miembro_id=self.anfitrion_id), 400,
                             'DATOS_INVALIDOS')
        self.assertEqual(self.permisos(self.anfitrion_id), (True, True))

    def test_version_obsoleta(self):
        respuesta = self.cambiar(version=self.version - 1)
        self.verificar_error(respuesta, 409, 'VERSION_OBSOLETA')
        self.assertEqual(respuesta.json()['detalles'], {'version_actual': self.version})

    def test_reintento_no_choca_con_su_propia_version(self):
        clave = uuid.uuid4()
        self.cambiar(True, False, clave=clave)
        respuesta = self.cambiar(True, False, clave=clave)
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json()['version'], self.version + 1)

    def test_misma_clave_con_otros_permisos_es_conflicto(self):
        clave = uuid.uuid4()
        self.cambiar(True, False, clave=clave)
        self.verificar_error(self.cambiar(False, True, clave=clave), 409, 'IDEMPOTENCIA_CONFLICTO')

    def desconectar_miembro(self):
        ParticipacionParty.objects.filter(usuario_id=self.miembro_id).update(
            salida_en=timezone.now(), motivo_salida='desconexion')

    def test_no_se_otorga_a_quien_no_esta_conectado(self):
        self.desconectar_miembro()
        self.verificar_error(self.cambiar(True, False), 409, 'PARTICIPANTE_NO_CONECTADO')
        self.assertEqual(self.permisos(), (False, False))

    def test_si_se_retira_a_quien_no_esta_conectado(self):
        version = self.cambiar(True, True).json()['version']
        self.desconectar_miembro()
        respuesta = self.cambiar(False, True, version=version)
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(self.permisos(), (False, True))

    def test_quien_no_esta_en_la_party(self):
        self.verificar_error(self.cambiar(miembro_id=uuid.uuid4()), 404, 'NO_ENCONTRADO')

    def test_party_que_no_existe(self):
        self.party_id = uuid.uuid4()
        self.verificar_error(self.cambiar(), 404, 'NO_ENCONTRADO')

    def test_party_finalizada(self):
        Party.objects.filter(id=self.party_id).update(finalizada_en=timezone.now())
        self.verificar_error(self.cambiar(), 410, 'PARTY_FINALIZADA')

    def test_permiso_que_no_es_booleano(self):
        cuerpo = {'puede_aportar': 'si', 'puede_modificar_cola': False,
                  'version_esperada': self.version}
        self.verificar_error(self.cambiar(cuerpo=cuerpo), 400, 'DATOS_INVALIDOS')

    def test_version_booleana(self):
        cuerpo = {'puede_aportar': True, 'puede_modificar_cola': False, 'version_esperada': True}
        self.verificar_error(self.cambiar(cuerpo=cuerpo), 400, 'DATOS_INVALIDOS')
