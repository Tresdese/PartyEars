from django.urls import path

from .views import (ColaView, ElementosView, ElementoView, MiColaView, MiElementoView,
                    MiReproduccionView, MisElementosView, MiTerminadaView, ReproduccionView,
                    TerminadaView)

PREFIJO = 'api/v1/queue/parties/<uuid:party_id>/cola'
PREFIJO_INDIVIDUAL = 'api/v1/queue/mi-cola'

urlpatterns = [
    path(PREFIJO, ColaView.as_view()),
    path(f'{PREFIJO}/elementos', ElementosView.as_view()),
    path(f'{PREFIJO}/elementos/<uuid:elemento_id>', ElementoView.as_view()),
    path(f'{PREFIJO}/elementos/<uuid:elemento_id>/terminada', TerminadaView.as_view()),
    path(f'{PREFIJO}/reproduccion', ReproduccionView.as_view()),
    path(PREFIJO_INDIVIDUAL, MiColaView.as_view()),
    path(f'{PREFIJO_INDIVIDUAL}/elementos', MisElementosView.as_view()),
    path(f'{PREFIJO_INDIVIDUAL}/elementos/<uuid:elemento_id>', MiElementoView.as_view()),
    path(f'{PREFIJO_INDIVIDUAL}/elementos/<uuid:elemento_id>/terminada',
         MiTerminadaView.as_view()),
    path(f'{PREFIJO_INDIVIDUAL}/reproduccion', MiReproduccionView.as_view()),
]
