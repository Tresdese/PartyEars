import uuid
from unittest.mock import patch

from django.db import DatabaseError

from apps.mensajeria.publicador import TIPO_OPERACION
from apps.parties.models import EventoSalida, MiembroParty
from .test_expulsion import PruebasExpulsion
from .utilidades import hacer_token


class RegistroOperacionesTests(PruebasExpulsion):
    """RF-34: logs puede seguir una revocación y un rechazo de la party."""

    def registros(self):
        return [e.datos for e in EventoSalida.objects.filter(
            agregado_id=self.party_id, tipo=TIPO_OPERACION).order_by('creado_en')]

    def cambiar_permisos(self, miembro_id, usuario_id=None, clave=None):
        return self.cliente.put(
            f'{self.URL}/{self.party_id}/miembros/{miembro_id}/permisos',
            {'puede_aportar': False, 'puede_modificar_cola': False,
             'version_esperada': self.party().version},
            format='json',
            HTTP_AUTHORIZATION=f'Bearer {hacer_token(usuario_id or self.anfitrion_id)}',
            HTTP_IDEMPOTENCY_KEY=str(clave or uuid.uuid4()))

    def test_una_revocacion_deja_actor_party_resultado_y_version(self):
        miembro = self.agregar()
        MiembroParty.objects.filter(usuario_id=miembro).update(puede_aportar=True)
        clave = uuid.uuid4()

        self.assertEqual(self.cambiar_permisos(miembro, clave=clave).status_code, 200)

        recibo = EventoSalida.objects.get(tipo=TIPO_OPERACION, datos__operacion='party.permisos')
        self.assertEqual(recibo.datos, {
            'actor_id': str(self.anfitrion_id), 'party_id': str(self.party_id),
            'operacion': 'party.permisos', 'resultado': 200, 'error': None, 'clave': str(clave)})
        self.assertEqual(recibo.version, self.party().version)

    def test_un_rechazo_queda_registrado_con_su_codigo(self):
        miembro, otro = self.agregar(), self.agregar()
        clave = uuid.uuid4()

        self.verificar_error(self.expulsar(otro, usuario_id=miembro, clave=clave),
                             403, 'NO_ES_ANFITRION')

        self.assertEqual(self.registros()[-1], {
            'actor_id': str(miembro), 'party_id': str(self.party_id),
            'operacion': 'party.expulsar', 'resultado': 403, 'error': 'NO_ES_ANFITRION',
            'clave': str(clave)})

    def test_sin_clave_valida_el_rechazo_se_registra_sin_ella(self):
        miembro = self.agregar()
        self.verificar_error(self.expulsar(miembro, clave='sin_clave'), 400, 'DATOS_INVALIDOS')
        self.assertEqual(self.registros()[-1]['clave'], None)

    def test_las_consultas_rechazadas_no_se_registran(self):
        antes = len(self.registros())
        self.verificar_error(self.consultar(uuid.uuid4()), 403, 'NO_ES_MIEMBRO')
        self.assertEqual(len(self.registros()), antes)

    def test_si_falla_el_registro_el_cliente_recibe_su_error(self):
        miembro = self.agregar()
        with patch('apps.parties.servicios.EventoSalida.objects.create',
                   side_effect=DatabaseError('caída')), self.assertLogs('apps.parties.errores'):
            respuesta = self.expulsar(miembro, usuario_id=miembro)
        self.verificar_error(respuesta, 403, 'NO_ES_ANFITRION')
