from django.urls import path
from .consumers import PartyConsumer

websocket_urlpatterns = [
    path('ws/v1/party/parties/<uuid:party_id>/', PartyConsumer.as_asgi()),
]