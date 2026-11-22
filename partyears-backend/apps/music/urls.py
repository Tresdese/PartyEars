from django.urls import path

from .views import CancionesView, RecursoAudioView, RecursoDetalleView

urlpatterns = [
    path('api/v1/music/canciones', CancionesView.as_view()),
    path('api/v1/music/recursos/<uuid:recurso_audio_id>', RecursoDetalleView.as_view()),
    path('api/v1/music/recursos/<uuid:recurso_audio_id>/audio', RecursoAudioView.as_view()),
]
