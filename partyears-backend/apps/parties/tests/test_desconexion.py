import uuid
from unittest import IsolatedAsyncioTestCase

from channels.db import database_sync_to_async
from django.test import override_settings
from django.utils import timezone

from apps.parties.models import EventoSalida, ParticipacionParty, Party
from apps.parties.servicios import desconectar_participante

from .utilidades import agregar_miembro, crear_party_en_bd, vaciar_tablas_party

TIPOS = ('miembro.desconectado', 'party.finalizada')


def leer_estado(party_id):
    party = Party.objects.get(id=party_id)
    return {
        'version': party.version,
        'finalizada_en': party.finalizada_en,
        'participaciones': {p.usuario_id: (p.salida_en, p.motivo_salida) for p in party.participaciones.all()},
        'miembros': {m.usuario_id: m.estado for m in party.miembros.all()},
        'eventos': [(e.tipo, e.datos) for e in EventoSalida.objects.filter(agregado_id=party_id, tipo__in=TIPOS).order_by('version')],
    }


class DesconectarParticipanteTests(IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        ajustes = override_settings(CHANNEL_LAYERS={'default': {'BACKEND': 'channels.layers.InMemoryChannelLayer'}})
        ajustes.enable()
        self.addCleanup(ajustes.disable)
        self.anfitrion_id = uuid.uuid4()
        self.party_id = await database_sync_to_async(crear_party_en_bd)(self.anfitrion_id)
        self.miembro_id = uuid.uuid4()
        await database_sync_to_async(agregar_miembro)(self.party_id, self.miembro_id)

    async def asyncTearDown(self):
        await database_sync_to_async(vaciar_tablas_party)()

    async def leer(self):
        return await database_sync_to_async(leer_estado)(self.party_id)

    async def desconectar(self, usuario_id):
        return await database_sync_to_async(desconectar_participante)(self.party_id, usuario_id)

    async def test_cierra_la_participacion_con_motivo_desconexion_y_avisa(self):
        antes = await self.leer()

        self.assertTrue(await self.desconectar(self.miembro_id))

        despues = await self.leer()
        salida_en, motivo = despues['participaciones'][self.miembro_id]
        self.assertIsNotNone(salida_en)
        self.assertEqual(motivo, 'desconexion')
        self.assertEqual(despues['eventos'], [('miembro.desconectado', {'usuario_id': str(self.miembro_id)})])
        self.assertEqual(despues['version'], antes['version'] + 1)

    async def test_conserva_la_membresia_y_la_party_sigue_activa(self):
        await self.desconectar(self.miembro_id)

        estado = await self.leer()
        self.assertEqual(estado['miembros'][self.miembro_id], 'habilitado')
        self.assertIsNone(estado['finalizada_en'])
        self.assertIsNone(estado['participaciones'][self.anfitrion_id][0])

    async def test_repetir_la_desconexion_no_hace_nada(self):
        self.assertTrue(await self.desconectar(self.miembro_id))
        despues = await self.leer()

        self.assertFalse(await self.desconectar(self.miembro_id))

        self.assertEqual(await self.leer(), despues)

    async def test_quien_ya_salio_no_se_marca_como_desconectado(self):
        await database_sync_to_async(ParticipacionParty.objects.filter(usuario_id=self.miembro_id).update)(salida_en=timezone.now(), motivo_salida='voluntaria')
        antes = await self.leer()

        self.assertFalse(await self.desconectar(self.miembro_id))

        self.assertEqual(await self.leer(), antes)
        self.assertEqual(antes['participaciones'][self.miembro_id][1], 'voluntaria')

    async def test_si_se_desconecta_el_anfitrion_y_queda_alguien_la_party_sigue(self):
        self.assertTrue(await self.desconectar(self.anfitrion_id))

        estado = await self.leer()
        self.assertIsNone(estado['finalizada_en'])
        self.assertEqual([tipo for tipo, _ in estado['eventos']], ['miembro.desconectado'])

    async def test_la_ultima_desconexion_finaliza_la_party(self):
        await self.desconectar(self.miembro_id)
        await self.desconectar(self.anfitrion_id)

        estado = await self.leer()
        self.assertIsNotNone(estado['finalizada_en'])
        self.assertEqual([tipo for tipo, _ in estado['eventos']], ['miembro.desconectado', 'miembro.desconectado', 'party.finalizada'])
        self.assertEqual(estado['eventos'][-1][1]['motivo'], 'sin_conectados')

    async def test_party_inexistente_o_finalizada_no_hace_nada(self):
        self.assertFalse(await database_sync_to_async(desconectar_participante)(uuid.uuid4(), self.miembro_id))

        await database_sync_to_async(Party.objects.filter(id=self.party_id).update)(finalizada_en=timezone.now())
        self.assertFalse(await self.desconectar(self.miembro_id))
        self.assertEqual((await self.leer())['eventos'], [])