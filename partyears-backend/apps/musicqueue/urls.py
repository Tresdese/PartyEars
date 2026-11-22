from django.urls import path

from .views import ColaView, ElementosView, ElementoView

PREFIJO = 'api/v1/queue/parties/<uuid:party_id>/cola'

urlpatterns = [
    path(PREFIJO, ColaView.as_view()),
    path(f'{PREFIJO}/elementos', ElementosView.as_view()),
    path(f'{PREFIJO}/elementos/<uuid:elemento_id>', ElementoView.as_view()),
]
