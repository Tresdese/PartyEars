from django.urls import path

from .views import PartiesView, PartyActualView

urlpatterns = [
    path('api/v1/party/parties', PartiesView.as_view()),
    path('api/v1/party/parties/actual', PartyActualView.as_view()),
]