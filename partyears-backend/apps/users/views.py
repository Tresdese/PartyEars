from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .servicios import (
    cerrar_sesion,
    consultar_usuarios_por_ids,
    iniciar_sesion,
    registrar_usuario,
    renovar_sesion,
)


class RegistroView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        resultado = registrar_usuario(request.data)
        return Response(resultado, status=201)


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        resultado = iniciar_sesion(request.data)
        return Response(resultado, status=200)


class RenovarView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        resultado = renovar_sesion(request.data)
        return Response(resultado, status=200)


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        cerrar_sesion(request.user, request.data)
        return Response(status=204)


class UsuariosView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        resultados = consultar_usuarios_por_ids(request.query_params.get('ids', ''))
        return Response({'resultados': resultados}, status=200)
