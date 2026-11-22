import uuid

from django.utils import timezone

from apps.parties.models import MiembroParty, ParticipacionParty, Party
from .utilidades import PruebasBase, agregar_miembro, hacer_token


class ConsultarPartyTests(PruebasBase):

    def setUp(self):
        super().setUp()
        self.anfitrion_id = uuid.uuid4()
        self.party_id = self.crear(self.anfitrion_id).json()['id']

    def consultar(self, usuario_id, party_id=None):
        return self.cliente.get(f'{self.URL}/{party_id or self.party_id}',
                                HTTP_AUTHORIZATION=f'Bearer {hacer_token(usuario_id)}')

    def verificar_error(self, respuesta, estado, codigo):
        self.assertEqual((respuesta.status_code, respuesta.json()['codigo']), (estado, codigo))

    def test_anfitrion_ve_la_party_con_su_codigo(self):
        respuesta = self.consultar(self.anfitrion_id)
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json()['anfitrion_id'], str(self.anfitrion_id))
        self.assertIsNotNone(respuesta.json()['codigo'])

    def test_miembro_conectado_la_ve_sin_codigo(self):
        usuario_id = uuid.uuid4()
        agregar_miembro(self.party_id, usuario_id)
        respuesta = self.consultar(usuario_id)
        self.assertEqual(respuesta.status_code, 200)
        self.assertIsNone(respuesta.json()['codigo'])

    def test_quien_no_es_miembro_recibe_no_es_miembro(self):
        self.verificar_error(self.consultar(uuid.uuid4()), 403, 'NO_ES_MIEMBRO')

    def test_miembro_que_ya_salio_recibe_no_es_miembro(self):
        usuario_id = uuid.uuid4()
        agregar_miembro(self.party_id, usuario_id)
        ParticipacionParty.objects.filter(usuario_id=usuario_id).update(
            salida_en=timezone.now(), motivo_salida='voluntaria')
        self.verificar_error(self.consultar(usuario_id), 403, 'NO_ES_MIEMBRO')

    def test_expulsado_recibe_no_es_miembro(self):
        usuario_id = uuid.uuid4()
        agregar_miembro(self.party_id, usuario_id)
        MiembroParty.objects.filter(usuario_id=usuario_id).update(estado='expulsado')
        self.verificar_error(self.consultar(usuario_id), 403, 'NO_ES_MIEMBRO')

    def test_party_que_no_existe(self):
        self.verificar_error(self.consultar(self.anfitrion_id, uuid.uuid4()), 404, 'NO_ENCONTRADO')

    def test_party_finalizada(self):
        Party.objects.filter(id=self.party_id).update(finalizada_en=timezone.now())
        self.verificar_error(self.consultar(self.anfitrion_id), 410, 'PARTY_FINALIZADA')

    def test_sin_token(self):
        respuesta = self.cliente.get(f'{self.URL}/{self.party_id}')
        self.verificar_error(respuesta, 401, 'TOKEN_INVALIDO')
