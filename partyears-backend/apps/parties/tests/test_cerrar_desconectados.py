import uuid
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import TransactionTestCase
from django.utils import timezone

from apps.parties.models import AnfitrionParty, ParticipacionParty, Party
from apps.parties.servicios import cerrar_participaciones_abiertas
from .utilidades import agregar_miembro, crear_party_en_bd, vaciar_tablas_party


class CerrarDesconectadosTests(TransactionTestCase):
    """The backend moved to another machine: whoever was inside must not stay as a ghost."""

    def tearDown(self):
        vaciar_tablas_party()

    def test_cierra_a_todos_y_la_party_termina_sola(self):
        anfitrion, miembro = uuid.uuid4(), uuid.uuid4()
        party_id = crear_party_en_bd(anfitrion)
        agregar_miembro(party_id, miembro)

        with patch('apps.parties.servicios.publicar'):
            call_command('cerrar_desconectados', stdout=StringIO())

        abiertas = ParticipacionParty.objects.filter(party_id=party_id, salida_en__isnull=True)
        self.assertFalse(abiertas.exists())
        motivos = set(ParticipacionParty.objects.filter(party_id=party_id)
                      .values_list('motivo_salida', flat=True))
        self.assertEqual(motivos, {'desconexion'})
        self.assertIsNotNone(Party.objects.get(id=party_id).finalizada_en)

    def test_no_toca_parties_terminadas_y_cuenta_las_cerradas(self):
        terminada = crear_party_en_bd(uuid.uuid4())
        Party.objects.filter(id=terminada).update(finalizada_en=timezone.now())
        activa = crear_party_en_bd(uuid.uuid4())

        with patch('apps.parties.servicios.publicar'):
            self.assertEqual(cerrar_participaciones_abiertas(), 1)

        self.assertTrue(ParticipacionParty.objects
                        .filter(party_id=terminada, salida_en__isnull=True).exists())
        self.assertEqual(AnfitrionParty.objects.filter(party_id=activa).count(), 1)
