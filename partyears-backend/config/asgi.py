from django.conf import settings
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter # noqa: E402

django_asgi = get_asgi_application()

rutas = {'http': django_asgi}
if 'apps.parties' in settings.INSTALLED_APPS:
    from apps.parties.routing import websocket_urlpatterns
    rutas['websocket'] = URLRouter(websocket_urlpatterns)

application = ProtocolTypeRouter(rutas)