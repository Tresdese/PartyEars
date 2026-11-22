import re

from django.http import FileResponse, HttpResponse
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .errores import ErrorApi
from .servicios import buscar_canciones, obtener_detalle_recurso, resolver_archivo_recurso

_PATRON_RANGE = re.compile(r'^bytes=(\d*)-(\d*)$')


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

        with open(ruta, 'rb') as f:
            f.seek(inicio)
            fragmento = f.read(longitud)

        respuesta = HttpResponse(fragmento, status=206, content_type=recurso.mime_type)
        respuesta['Content-Range'] = f'bytes {inicio}-{fin}/{tamano}'
        respuesta['Content-Length'] = str(longitud)
        respuesta['Accept-Ranges'] = 'bytes'
        return respuesta
