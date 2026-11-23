import tempfile
import time
import uuid
from pathlib import Path

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from django.core.management import call_command
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.music.management.commands.cargar_catalogo import generar_carpeta_muestra
from apps.music.models import Artista, Cancion, RecursoAudio


def _generar_par_claves():
    privada = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    publica = privada.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode('utf-8')
    return privada, publica


CLAVE_PRIVADA_TEST, CLAVE_PUBLICA_TEST = _generar_par_claves()


def _hacer_token():
    ahora = int(time.time())
    payload = {
        'sub': str(uuid.uuid4()),
        'nombre_usuario': 'axel',
        'sid': str(uuid.uuid4()),
        'iat': ahora,
        'exp': ahora + 300,
    }
    return jwt.encode(payload, CLAVE_PRIVADA_TEST, algorithm='RS256')


@override_settings(JWT_CLAVE_PUBLICA=CLAVE_PUBLICA_TEST)
class CatalogoMusicaTests(TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.media_dir = Path(self.tmp_dir.name) / 'media'
        self.origen_dir = Path(self.tmp_dir.name) / 'origen'
        self.media_dir.mkdir(parents=True, exist_ok=True)
        self.cliente = APIClient()
        self.cliente.credentials(HTTP_AUTHORIZATION=f'Bearer {_hacer_token()}')

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_comando_carga_al_menos_20_pistas_con_metadatos_completos(self):
        with override_settings(MEDIA_ROOT=self.media_dir):
            generar_carpeta_muestra(self.origen_dir)
            call_command('cargar_catalogo', str(self.origen_dir))

        self.assertGreaterEqual(RecursoAudio.objects.count(), 20)
        self.assertEqual(Cancion.objects.count(), 20)
        self.assertGreaterEqual(Artista.objects.count(), 10)

        for recurso in RecursoAudio.objects.select_related('cancion').all():
            self.assertTrue(recurso.cancion.titulo.strip())
            self.assertGreater(recurso.cancion.artistas.count(), 0)
            self.assertGreater(recurso.duracion_ms, 0)
            self.assertEqual(recurso.formato, 'wav')
            self.assertEqual(recurso.mime_type, 'audio/wav')

        # Verificar que una canción con variante instrumental tenga ambas variantes
        daft = Cancion.objects.get(titulo='One More Time')
        tipos = set(daft.variantes.values_list('tipo', flat=True))
        self.assertEqual(tipos, {'original', 'instrumental'})

    def test_comando_es_idempotente_al_ejecutarse_dos_veces(self):
        with override_settings(MEDIA_ROOT=self.media_dir):
            generar_carpeta_muestra(self.origen_dir)
            call_command('cargar_catalogo', str(self.origen_dir))
            total_inicial = RecursoAudio.objects.count()
            call_command('cargar_catalogo', str(self.origen_dir))
            self.assertEqual(RecursoAudio.objects.count(), total_inicial)

    def test_la_busqueda_omite_canciones_sin_archivo_en_esta_maquina(self):
        with override_settings(MEDIA_ROOT=self.media_dir):
            generar_carpeta_muestra(self.origen_dir)
            call_command('cargar_catalogo', str(self.origen_dir))
            # Another machine's copy of the catalog lacks this file (demo package, T-14).
            (self.media_dir / 'catalogo' / 'Queen - Bohemian Rhapsody.wav').unlink()

            cuerpo = self.cliente.get('/api/v1/music/canciones?pagina=1').json()
            self.assertEqual(cuerpo['total'], 19)
            titulos = [c['titulo'] for c in
                       self.cliente.get('/api/v1/music/canciones?q=queen').json()['resultados']]
            self.assertEqual(titulos, ["Don't Stop Me Now"])

    def test_endpoints_busqueda_detalle_y_streaming_por_rangos(self):
        with override_settings(MEDIA_ROOT=self.media_dir):
            generar_carpeta_muestra(self.origen_dir)
            call_command('cargar_catalogo', str(self.origen_dir))

            # Búsqueda paginada (20 por página)
            resp_lista = self.cliente.get('/api/v1/music/canciones?pagina=1')
            self.assertEqual(resp_lista.status_code, 200)
            cuerpo = resp_lista.json()
            self.assertEqual(cuerpo['total'], 20)
            self.assertEqual(len(cuerpo['resultados']), 20)

            # Filtro por artista o título
            resp_busqueda = self.cliente.get('/api/v1/music/canciones?q=daft')
            self.assertEqual(resp_busqueda.status_code, 200)
            resultados_daft = resp_busqueda.json()['resultados']
            self.assertEqual(len(resultados_daft), 2)

            one_more = next(c for c in resultados_daft if c['titulo'] == 'One More Time')
            self.assertEqual(len(one_more['variantes']), 2)
            recurso_id = one_more['variantes'][0]['recurso_audio_id']

            # Detalle de recurso
            resp_det = self.cliente.get(f'/api/v1/music/recursos/{recurso_id}')
            self.assertEqual(resp_det.status_code, 200)
            self.assertEqual(resp_det.json()['cancion']['titulo'], 'One More Time')

            # Streaming con cabecera Range -> 206 Partial Content
            resp_audio = self.cliente.get(
                f'/api/v1/music/recursos/{recurso_id}/audio',
                HTTP_RANGE='bytes=0-1023',
            )
            self.assertEqual(resp_audio.status_code, 206)
            self.assertEqual(resp_audio['Accept-Ranges'], 'bytes')
            self.assertTrue(resp_audio['Content-Range'].startswith('bytes 0-1023/'))
            self.assertEqual(len(b''.join(resp_audio.streaming_content)), 1024)

            # A range in the middle returns exactly those bytes, read in chunks
            completo = b''.join(self.cliente.get(
                f'/api/v1/music/recursos/{recurso_id}/audio').streaming_content)
            resp_medio = self.cliente.get(f'/api/v1/music/recursos/{recurso_id}/audio',
                                          HTTP_RANGE='bytes=1000-')
            self.assertEqual(resp_medio.status_code, 206)
            self.assertEqual(b''.join(resp_medio.streaming_content), completo[1000:])
            self.assertEqual(resp_medio['Content-Length'], str(len(completo) - 1000))
