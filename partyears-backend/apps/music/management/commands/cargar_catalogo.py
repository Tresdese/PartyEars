import math
import struct
import wave
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.music.servicios import cargar_desde_carpeta

PISTAS_MUESTRA = [
    ("Daft Punk - One More Time.wav", 520, 3),
    ("Daft Punk - Harder Better Faster Stronger.wav", 440, 3),
    ("Radiohead - Creep.wav", 392, 4),
    ("Radiohead - Karma Police.wav", 349, 4),
    ("Tame Impala - The Less I Know The Better.wav", 494, 3),
    ("Tame Impala - Let It Happen.wav", 466, 4),
    ("Gorillaz - Feel Good Inc.wav", 415, 3),
    ("Gorillaz - Clint Eastwood.wav", 370, 4),
    ("Queen - Bohemian Rhapsody.wav", 587, 5),
    ("Queen - Don't Stop Me Now.wav", 554, 3),
    ("The Weeknd - Blinding Lights.wav", 622, 3),
    ("The Weeknd - Save Your Tears.wav", 587, 3),
    ("Arctic Monkeys - Do I Wanna Know.wav", 330, 4),
    ("Arctic Monkeys - R U Mine.wav", 311, 3),
    ("Muse - Starlight.wav", 440, 4),
    ("Muse - Supermassive Black Hole.wav", 392, 3),
    ("RADWIMPS - Zenzenzense.wav", 523, 4),
    ("RADWIMPS - Sparkle.wav", 494, 5),
    ("Ado - Usseewa.wav", 659, 3),
    ("Ado - New Genesis.wav", 587, 3),
    ("Daft Punk - One More Time (Instrumental).wav", 520, 3),
    ("The Weeknd - Blinding Lights (Instrumental).wav", 622, 3),
]


def generar_carpeta_muestra(destino: Path) -> Path:
    destino.mkdir(parents=True, exist_ok=True)
    sample_rate = 8000
    for nombre_archivo, frecuencia, segundos in PISTAS_MUESTRA:
        ruta = destino / nombre_archivo
        total_frames = sample_rate * segundos
        with wave.open(str(ruta), 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            muestras = bytearray()
            for n in range(total_frames):
                valor = int(8000 * math.sin(2 * math.pi * frecuencia * n / sample_rate))
                muestras.extend(struct.pack('<h', valor))
            wf.writeframes(bytes(muestras))
    return destino


class Command(BaseCommand):
    help = 'Carga canciones, artistas y recursos de audio con sus metadatos desde una carpeta del servidor.'

    def add_arguments(self, parser):
        parser.add_argument(
            'carpeta',
            nargs='?',
            default=str(Path(settings.MEDIA_ROOT) / 'origen_catalogo'),
            help='Ruta de la carpeta del servidor que contiene las pistas de audio.',
        )
        parser.add_argument(
            '--generar-muestra',
            action='store_true',
            help='Genera 22 pistas de audio WAV válidas en la carpeta antes de importarlas.',
        )
        parser.add_argument(
            '--en-sitio',
            action='store_true',
            help='Referencia los archivos directamente en su carpeta original sin copiarlos a MEDIA_ROOT/catalogo.',
        )

    def handle(self, *args, **options):
        carpeta = Path(options['carpeta'])

        if options['generar_muestra']:
            generar_carpeta_muestra(carpeta)
            self.stdout.write(f'Generadas {len(PISTAS_MUESTRA)} pistas de muestra en: {carpeta}')

        try:
            resumen = cargar_desde_carpeta(carpeta, en_sitio=options['en_sitio'])
        except FileNotFoundError as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(
            self.style.SUCCESS(
                f"Catálogo actualizado: {resumen['archivos_procesados']} pistas procesadas "
                f"({resumen['canciones_creadas']} canciones nuevas, "
                f"{resumen['canciones_actualizadas']} actualizadas, "
                f"{resumen['recursos_creados']} recursos nuevos)."
            )
        )
