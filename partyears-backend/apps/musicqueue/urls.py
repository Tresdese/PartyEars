from django.urls import path

from .views import ColaView, ElementosView, ElementoView, ReproduccionView, TerminadaView

PREFIJO = 'api/v1/queue/parties/<uuid:party_id>/cola'

urlpatterns = [
    path(PREFIJO, ColaView.as_view()),
    path(f'{PREFIJO}/elementos', ElementosView.as_view()),
    path(f'{PREFIJO}/elementos/<uuid:elemento_id>', ElementoView.as_view()),
    path(f'{PREFIJO}/elementos/<uuid:elemento_id>/terminada', TerminadaView.as_view()),
    path(f'{PREFIJO}/reproduccion', ReproduccionView.as_view()),
]
