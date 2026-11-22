from .base import *
from .base import BASE_DIR, INSTALLED_APPS, database
import os

INSTALLED_APPS = INSTALLED_APPS + ['apps.music']

DATABASES = database('music')

MEDIA_ROOT = Path(os.environ.get('MUSIC_MEDIA_ROOT', BASE_DIR / 'media'))

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': ['apps.music.autenticacion.JWTAuthentication'],
    'DEFAULT_PERMISSION_CLASSES': ['rest_framework.permissions.IsAuthenticated'],
    'DEFAULT_RENDERER_CLASSES': ['rest_framework.renderers.JSONRenderer'],
    'DEFAULT_PARSER_CLASSES': ['rest_framework.parsers.JSONParser'],
    'EXCEPTION_HANDLER': 'apps.music.errores.manejar_excepcion',
    'UNAUTHENTICATED_USER': None,
}

_ruta_publica = os.environ.get('JWT_CLAVE_PUBLICA_ARCHIVO', 'claves-dev/publica.pem')
JWT_CLAVE_PUBLICA = (
    (BASE_DIR / _ruta_publica).read_text(encoding='utf-8')
    if _ruta_publica and (BASE_DIR / _ruta_publica).exists()
    else ''
)
