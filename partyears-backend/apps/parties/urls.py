from django.urls import path

from .views import (FinalizarView, PartiesView, PartyActualView, PartyView, PermisosView, SalirView, UnirseView)

urlpatterns = [
    path('api/v1/party/parties', PartiesView.as_view()),
    path('api/v1/party/parties/actual', PartyActualView.as_view()),
    path('api/v1/party/parties/unirse', UnirseView.as_view()),
    path('api/v1/party/parties/<uuid:party_id>', PartyView.as_view()),
    path('api/v1/party/parties/<uuid:party_id>/miembros/<uuid:usuario_id>/permisos', PermisosView.as_view()),
    path('api/v1/party/parties/<uuid:party_id>/salir', SalirView.as_view()),
    path('api/v1/party/parties/<uuid:party_id>/finalizar', FinalizarView.as_view()),
]
