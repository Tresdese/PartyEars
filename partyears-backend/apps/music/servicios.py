import json
import math
import re
import shutil
import struct
import wave
from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.db.models import Prefetch, Q

from .errores import ErrorApi
from .models import Artista, Cancion, CancionArtista, RecursoAudio

FORMATOS_SOPORTADOS = {
    '.mp3': ('mp3', 'audio/mpeg'),
    '.wav': ('wav', 'audio/wav'),
    '.ogg': ('ogg', 'audio/ogg'),
    '.flac': ('flac', 'audio/flac'),
    '.m4a': ('m4a', 'audio/mp4'),
    '.aac': ('aac', 'audio/aac'),
}

TAMANO_PAGINA = 20

_PATRON_INSTRUMENTAL = re.compile(r'[\(\[\-_]\s*instrumental\s*[\)\]]?$', re.IGNORECASE)
_SEPARADOR_ARTISTAS = re.compile(r'\s*(?:,|&|\bfeat\.?\b|\bft\.?\b)\s*', re.IGNORECASE)


def _leer_id3v2(datos: bytes) -> tuple[dict, int]:
    """Lee etiquetas básicas ID3v2 (TIT2, TPE1) y devuelve (metadatos, offset_audio)."""
    meta = {}
    if len(datos) < 10 or datos[:3] != b'ID3':
        return meta, 0

    version = datos[3]
    tamano = (
        ((datos[6] & 0x7F) << 21)
        | ((datos[7] & 0x7F) << 14)
        | ((datos[8] & 0x7F) << 7)
        | (datos[9] & 0x7F)
    )
    fin = min(len(datos), 10 + tamano)
    pos = 10

    while pos + 10 <= fin and version in (3, 4):
        frame_id = datos[pos : pos + 4]
        if frame_id == b'\x00\x00\x00\x00':
            break
        if version == 4:
            frame_size = (
                ((datos[pos + 4] & 0x7F) << 21)
                | ((datos[pos + 5] & 0x7F) << 14)
                | ((datos[pos + 6] & 0x7F) << 7)
                | (datos[pos + 7] & 0x7F)
            )
        else:
            frame_size = struct.unpack('>I', datos[pos + 4 : pos + 8])[0]

        if frame_size <= 0 or pos + 10 + frame_size > fin:
            break

        cuerpo = datos[pos + 10 : pos + 10 + frame_size]
        if frame_id in (b'TIT2', b'TPE1') and len(cuerpo) > 1:
            cod = cuerpo[0]
            crudo = cuerpo[1:]
            try:
                if cod == 0:
                    texto = crudo.decode('latin-1', errors='ignore')
                elif cod in (1, 2):
                    texto = crudo.decode('utf-16', errors='ignore')
                else:
                    texto = crudo.decode('utf-8', errors='ignore')
                texto = texto.replace('\x00', '').strip()
                if texto:
                    if frame_id == b'TIT2':
                        meta['titulo'] = texto
                    elif frame_id == b'TPE1':
                        meta['artistas'] = [a.strip() for a in _SEPARADOR_ARTISTAS.split(texto) if a.strip()]
            except UnicodeDecodeError:
                pass
        pos += 10 + frame_size

    return meta, fin


def _leer_id3v1(datos: bytes) -> dict:
    meta = {}
    if len(datos) >= 128 and datos[-128:-125] == b'TAG':
        titulo = datos[-125:-95].decode('latin-1', errors='ignore').replace('\x00', '').strip()
        artista = datos[-95:-65].decode('latin-1', errors='ignore').replace('\x00', '').strip()
        if titulo:
            meta['titulo'] = titulo
        if artista:
            meta['artistas'] = [a.strip() for a in _SEPARADOR_ARTISTAS.split(artista) if a.strip()]
    return meta


def _duracion_mp3_ms(datos: bytes, offset_audio: int) -> int:
    bitrates_v1_l3 = [0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320, 0]
    bitrates_v2_l3 = [0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160, 0]
    rates_v1 = [44100, 48000, 32000]
    rates_v2 = [22050, 24000, 16000]
    rates_v25 = [11025, 12000, 8000]

    limite = min(len(datos) - 4, offset_audio + 65536)
    for i in range(offset_audio, max(offset_audio, limite)):
        if datos[i] == 0xFF and (datos[i + 1] & 0xE0) == 0xE0:
            ver_id = (datos[i + 1] >> 3) & 0x03
            layer = (datos[i + 1] >> 1) & 0x03
            br_idx = (datos[i + 2] >> 4) & 0x0F
            sr_idx = (datos[i + 2] >> 2) & 0x03
            if ver_id == 1 or layer != 1 or br_idx in (0, 15) or sr_idx == 3:
                continue

            if ver_id == 3:
                bitrate = bitrates_v1_l3[br_idx] * 1000
                sample_rate = rates_v1[sr_idx]
                samples_per_frame = 1152
            elif ver_id == 2:
                bitrate = bitrates_v2_l3[br_idx] * 1000
                sample_rate = rates_v2[sr_idx]
                samples_per_frame = 576
            else:
                bitrate = bitrates_v2_l3[br_idx] * 1000
                sample_rate = rates_v25[sr_idx]
                samples_per_frame = 576

            cabecera_xing = datos[i + 4 : i + 40]
            for marca in (b'Xing', b'Info'):
                idx_m = cabecera_xing.find(marca)
                if idx_m != -1 and idx_m + 12 <= len(cabecera_xing):
                    flags = struct.unpack('>I', cabecera_xing[idx_m + 4 : idx_m + 8])[0]
                    if flags & 0x01:
                        frames = struct.unpack('>I', cabecera_xing[idx_m + 8 : idx_m + 12])[0]
                        if frames > 0:
                            return max(1, int(round((frames * samples_per_frame / sample_rate) * 1000)))

            bytes_audio = max(1, len(datos) - i)
            return max(1, int(round((bytes_audio * 8 / bitrate) * 1000)))

    return 180000


def _duracion_flac_ms(datos: bytes) -> int:
    if len(datos) >= 42 and datos[:4] == b'fLaC' and (datos[4] & 0x7F) == 0:
        sr_y_samples = struct.unpack('>Q', datos[18:26])[0]
        sample_rate = (sr_y_samples >> 44) & 0xFFFFF
        total_samples = sr_y_samples & 0xFFFFFFFFF
        if sample_rate > 0 and total_samples > 0:
            return max(1, int(round((total_samples / sample_rate) * 1000)))
    return 180000


def _duracion_ogg_ms(datos: bytes) -> int:
    sample_rate = 0
    idx_vorbis = datos.find(b'\x01vorbis')
    if idx_vorbis != -1 and idx_vorbis + 16 <= len(datos):
        sample_rate = struct.unpack('<I', datos[idx_vorbis + 12 : idx_vorbis + 16])[0]

    ultimo_oggs = datos.rfind(b'OggS')
    if sample_rate > 0 and ultimo_oggs != -1 and ultimo_oggs + 14 <= len(datos):
        granule = struct.unpack('<Q', datos[ultimo_oggs + 6 : ultimo_oggs + 14])[0]
        if granule > 0:
            return max(1, int(round((granule / sample_rate) * 1000)))
    return 180000


def extraer_metadatos_archivo(ruta: Path, metadatos_json: dict | None = None) -> dict:
    """Extrae título, artistas, duración (ms), formato, mime_type y tipo de variante."""
    ext = ruta.suffix.lower()
    formato, mime_type = FORMATOS_SOPORTADOS[ext]
    datos = ruta.read_bytes()

    meta_embebida = {}
    offset_audio = 0
    if formato == 'mp3':
        meta_embebida, offset_audio = _leer_id3v2(datos)
        if not meta_embebida:
            meta_embebida = _leer_id3v1(datos)

    nombre_base = ruta.stem.strip()
    tipo = RecursoAudio.TIPO_ORIGINAL
    if _PATRON_INSTRUMENTAL.search(nombre_base):
        tipo = RecursoAudio.TIPO_INSTRUMENTAL
        nombre_base = _PATRON_INSTRUMENTAL.sub('', nombre_base).strip()

    if ' - ' in nombre_base:
        parte_artistas, parte_titulo = nombre_base.split(' - ', 1)
        artistas_nombre = [a.strip() for a in _SEPARADOR_ARTISTAS.split(parte_artistas) if a.strip()]
        titulo_nombre = parte_titulo.strip()
    else:
        artistas_nombre = ['Artista Desconocido']
        titulo_nombre = nombre_base

    if formato == 'wav':
        try:
            with wave.open(str(ruta), 'rb') as wf:
                frames = wf.getnframes()
                rate = wf.getframerate()
                duracion_ms = max(1, int(round((frames / rate) * 1000))) if rate > 0 else 180000
        except wave.Error:
            duracion_ms = 180000
    elif formato == 'mp3':
        duracion_ms = _duracion_mp3_ms(datos, offset_audio)
    elif formato == 'flac':
        duracion_ms = _duracion_flac_ms(datos)
    elif formato == 'ogg':
        duracion_ms = _duracion_ogg_ms(datos)
    else:
        duracion_ms = 180000

    override = metadatos_json or {}
    titulo = str(override.get('titulo') or meta_embebida.get('titulo') or titulo_nombre).strip()
    artistas = override.get('artistas') or meta_embebida.get('artistas') or artistas_nombre
    if isinstance(artistas, str):
        artistas = [a.strip() for a in _SEPARADOR_ARTISTAS.split(artistas) if a.strip()]
    artistas = [a.strip() for a in artistas if isinstance(a, str) and a.strip()] or ['Artista Desconocido']

    if override.get('duracion_ms'):
        duracion_ms = max(1, int(override['duracion_ms']))

    tipo_final = str(override.get('tipo') or tipo).strip().lower()
    if tipo_final not in (RecursoAudio.TIPO_ORIGINAL, RecursoAudio.TIPO_INSTRUMENTAL):
        tipo_final = RecursoAudio.TIPO_ORIGINAL

    return {
        'titulo': titulo,
        'artistas': artistas,
        'duracion_ms': duracion_ms,
        'formato': formato,
        'mime_type': mime_type,
        'tipo': tipo_final,
        'tamano_bytes': len(datos),
    }


def _obtener_o_crear_artista(nombre: str) -> Artista:
    existente = Artista.objects.filter(nombre__iexact=nombre).first()
    if existente is not None:
        return existente
    return Artista.objects.create(nombre=nombre)


def _resolver_ruta_destino(archivo_origen: Path, carpeta_origen: Path, en_sitio: bool) -> str:
    media_root = Path(settings.MEDIA_ROOT).resolve()
    origen_resuelto = archivo_origen.resolve()

    if en_sitio:
        try:
            return str(origen_resuelto.relative_to(media_root)).replace('\\', '/')
        except ValueError:
            return str(origen_resuelto)

    try:
        relativa = origen_resuelto.relative_to(carpeta_origen.resolve())
    except ValueError:
        relativa = Path(archivo_origen.name)

    destino = media_root / 'catalogo' / relativa
    destino.parent.mkdir(parents=True, exist_ok=True)
    if origen_resuelto != destino.resolve():
        shutil.copy2(origen_resuelto, destino)
    return str(destino.relative_to(media_root)).replace('\\', '/')


@transaction.atomic
def cargar_desde_carpeta(carpeta: str | Path, en_sitio: bool = False) -> dict:
    """Importa pistas de audio y sus metadatos desde una carpeta del servidor."""
    raiz = Path(carpeta)
    if not raiz.exists() or not raiz.is_dir():
        raise FileNotFoundError(f'La carpeta no existe: {raiz}')

    catalogo_json = {}
    archivo_meta = raiz / 'catalogo.json'
    if archivo_meta.exists():
        contenido = json.loads(archivo_meta.read_text(encoding='utf-8'))
        if isinstance(contenido, dict):
            catalogo_json = contenido

    archivos_audio = sorted(
        p for p in raiz.rglob('*') if p.is_file() and p.suffix.lower() in FORMATOS_SOPORTADOS
    )

    resumen = {
        'archivos_procesados': 0,
        'canciones_creadas': 0,
        'canciones_actualizadas': 0,
        'recursos_creados': 0,
        'recursos_actualizados': 0,
    }

    for archivo in archivos_audio:
        clave_rel = str(archivo.relative_to(raiz)).replace('\\', '/')
        override = catalogo_json.get(clave_rel) or catalogo_json.get(archivo.name)
        meta = extraer_metadatos_archivo(archivo, metadatos_json=override)

        artistas_obj = [_obtener_o_crear_artista(nombre) for nombre in meta['artistas']]
        primer_artista = artistas_obj[0]

        cancion = (
            Cancion.objects.filter(
                titulo__iexact=meta['titulo'],
                creditos__artista=primer_artista,
                creditos__orden=1,
            )
            .distinct()
            .first()
        )

        if cancion is None:
            cancion = Cancion.objects.create(
                titulo=meta['titulo'],
                duracion_ms=meta['duracion_ms'],
            )
            resumen['canciones_creadas'] += 1
        else:
            if meta['tipo'] == RecursoAudio.TIPO_ORIGINAL and cancion.duracion_ms != meta['duracion_ms']:
                cancion.duracion_ms = meta['duracion_ms']
                cancion.save(update_fields=['duracion_ms'])
            resumen['canciones_actualizadas'] += 1

        CancionArtista.objects.filter(cancion=cancion).delete()
        for indice, artista in enumerate(artistas_obj, start=1):
            CancionArtista.objects.create(cancion=cancion, artista=artista, orden=indice)

        ruta_guardada = _resolver_ruta_destino(archivo, raiz, en_sitio=en_sitio)

        recurso, creado = RecursoAudio.objects.update_or_create(
            cancion=cancion,
            tipo=meta['tipo'],
            defaults={
                'formato': meta['formato'],
                'mime_type': meta['mime_type'],
                'ruta_archivo': ruta_guardada,
                'tamano_bytes': meta['tamano_bytes'],
                'duracion_ms': meta['duracion_ms'],
                'disponible': True,
            },
        )
        if creado:
            resumen['recursos_creados'] += 1
        else:
            resumen['recursos_actualizados'] += 1

        resumen['archivos_procesados'] += 1

    return resumen


def _serializar_cancion(cancion: Cancion) -> dict:
    creditos = sorted(cancion.creditos.all(), key=lambda c: c.orden)
    artistas = [{'id': str(c.artista.id), 'nombre': c.artista.nombre} for c in creditos]
    variantes = [
        {
            'recurso_audio_id': str(v.id),
            'tipo': v.tipo,
            'disponible': v.disponible,
        }
        for v in sorted(cancion.variantes.all(), key=lambda r: (0 if r.tipo == 'original' else 1))
    ]
    return {
        'id': str(cancion.id),
        'titulo': cancion.titulo,
        'duracion_ms': cancion.duracion_ms,
        'artistas': artistas,
        'variantes': variantes,
    }


def buscar_canciones(consulta: str = '', pagina_raw: str = '1') -> dict:
    try:
        pagina = int(pagina_raw)
        if pagina < 1:
            pagina = 1
    except (TypeError, ValueError):
        pagina = 1

    qs = Cancion.objects.all().prefetch_related(
        Prefetch('creditos', queryset=CancionArtista.objects.select_related('artista').order_by('orden')),
        'variantes',
    )

    texto = (consulta or '').strip()
    if texto:
        qs = qs.filter(Q(titulo__icontains=texto) | Q(artistas__nombre__icontains=texto)).distinct()

    qs = qs.order_by('titulo', 'id')
    total = qs.count()
    total_paginas = math.ceil(total / TAMANO_PAGINA) if total > 0 else 0

    inicio = (pagina - 1) * TAMANO_PAGINA
    fin = inicio + TAMANO_PAGINA
    resultados = [_serializar_cancion(c) for c in qs[inicio:fin]]

    return {
        'resultados': resultados,
        'pagina': pagina,
        'total_paginas': total_paginas,
        'total': total,
    }


def obtener_detalle_recurso(recurso_id) -> dict:
    recurso = (
        RecursoAudio.objects.select_related('cancion')
        .prefetch_related(
            Prefetch(
                'cancion__creditos',
                queryset=CancionArtista.objects.select_related('artista').order_by('orden'),
            )
        )
        .filter(id=recurso_id)
        .first()
    )
    if recurso is None:
        raise ErrorApi(404, 'NO_ENCONTRADO', 'El recurso de audio solicitado no existe.')

    creditos = sorted(recurso.cancion.creditos.all(), key=lambda c: c.orden)
    artistas = [{'id': str(c.artista.id), 'nombre': c.artista.nombre} for c in creditos]

    return {
        'recurso_audio_id': str(recurso.id),
        'tipo': recurso.tipo,
        'disponible': recurso.disponible,
        'cancion': {
            'id': str(recurso.cancion.id),
            'titulo': recurso.cancion.titulo,
            'duracion_ms': recurso.cancion.duracion_ms,
            'artistas': artistas,
        },
    }


def resolver_archivo_recurso(recurso_id) -> tuple[RecursoAudio, Path]:
    recurso = RecursoAudio.objects.filter(id=recurso_id).first()
    if recurso is None:
        raise ErrorApi(404, 'NO_ENCONTRADO', 'El recurso de audio solicitado no existe.')

    if not recurso.disponible:
        raise ErrorApi(410, 'AUDIO_NO_DISPONIBLE', 'Este audio ya no está disponible.')

    ruta = Path(recurso.ruta_archivo)
    if not ruta.is_absolute():
        ruta = Path(settings.MEDIA_ROOT) / ruta

    if not ruta.exists() or not ruta.is_file():
        raise ErrorApi(410, 'AUDIO_NO_DISPONIBLE', 'El archivo de audio no se encuentra en el servidor.')

    return recurso, ruta
