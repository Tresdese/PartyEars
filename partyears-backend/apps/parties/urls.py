from django.urls import path

from .views import PartiesView, PartyActualView, PartyView, UnirseView

urlpatterns = [
    path('api/v1/party/parties', PartiesView.as_view()),
    path('api/v1/party/parties/actual', PartyActualView.as_view()),
    path('api/v1/party/parties/unirse', UnirseView.as_view()),
    path('api/v1/party/parties/<uuid:party_id>', PartyView.as_view()),
]