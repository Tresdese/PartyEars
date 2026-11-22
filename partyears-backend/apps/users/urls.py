from django.urls import path

from .views import LoginView, LogoutView, RegistroView, RenovarView, UsuariosView

urlpatterns = [
    path('api/v1/auth/registro', RegistroView.as_view()),
    path('api/v1/auth/login', LoginView.as_view()),
    path('api/v1/auth/renovar', RenovarView.as_view()),
    path('api/v1/auth/logout', LogoutView.as_view()),
    path('api/v1/auth/usuarios', UsuariosView.as_view()),
]
