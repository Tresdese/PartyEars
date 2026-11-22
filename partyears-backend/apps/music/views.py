import re

from django.http import FileResponse, HttpResponse, StreamingHttpResponse
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .errores import ErrorApi
from .servicios import buscar_canciones, obtener_detalle_recurso, resolver_archivo_recurso

_PATRON_RANGE = re.compile(r'^bytes=(\d*)-(\d*)$')
_TROZO = 64 * 1024


def _leer_trozos(ruta, inicio, longitud):
    # Chunks instead of reading the whole range: players ask for "bytes=N-", the rest of a
    # 30-50 MB FLAC, and 20 phones at once would hold over a gigabyte in memory.
    with open(ruta, 'rb') as archivo:
        archivo.seek(inicio)
        while longitud > 0:
            trozo = archivo.read(min(_TROZO, longitud))
            if not trozo:
                return
            longitud -= len(trozo)
            yield trozo


class CancionesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        consulta = request.query_params.get('q', '')
        pagina = request.query_params.get('pagina', '1')
        resultado = buscar_canciones(consulta=consulta, pagina_raw=pagina)
        return Response(resultado, status=200)


class RecursoDetalleView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, recurso_audio_id):
        detalle = obtener_detalle_recurso(recurso_audio_id)
        return Response(detalle, status=200)


class RecursoAudioView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, recurso_audio_id):
        recurso, ruta = resolver_archivo_recurso(recurso_audio_id)
        tamano = ruta.stat().st_size
        rango = request.headers.get('Range', '').strip()

        if not rango:
            respuesta = FileResponse(open(ruta, 'rb'), content_type=recurso.mime_type)
            respuesta['Content-Length'] = str(tamano)
            respuesta['Accept-Ranges'] = 'bytes'
            return respuesta

        coincidencia = _PATRON_RANGE.match(rango)
        if not coincidencia:
            raise ErrorApi(400, 'DATOS_INVALIDOS', 'Cabecera Range inválida.')

        inicio_str, fin_str = coincidencia.groups()
        if not inicio_str and not fin_str:
            raise ErrorApi(400, 'DATOS_INVALIDOS', 'Cabecera Range inválida.')

        if inicio_str:
            inicio = int(inicio_str)
            fin = int(fin_str) if fin_str else tamano - 1
        else:
            ultimos = int(fin_str)
            inicio = max(0, tamano - ultimos)
            fin = tamano - 1

        if inicio >= tamano or fin < inicio:
            respuesta = HttpResponse(status=416)
            respuesta['Content-Range'] = f'bytes */{tamano}'
            return respuesta

        fin = min(fin, tamano - 1)
        longitud = fin - inicio + 1

        respuesta = StreamingHttpResponse(_leer_trozos(ruta, inicio, longitud), status=206,
                                          content_type=recurso.mime_type)
        respuesta['Content-Range'] = f'bytes {inicio}-{fin}/{tamano}'
        respuesta['Content-Length'] = str(longitud)
        respuesta['Accept-Ranges'] = 'bytes'
        return respuesta
