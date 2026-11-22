from .base import *
from .base import BASE_DIR, INSTALLED_APPS, database
import os

INSTALLED_APPS = INSTALLED_APPS + [
    'django.contrib.admin',
    'django.contrib.sessions',
    'django.contrib.messages',
    'apps.users',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

DATABASES = database('auth')

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': ['apps.users.autenticacion.JWTAuthentication'],
    'DEFAULT_PERMISSION_CLASSES': ['rest_framework.permissions.IsAuthenticated'],
    'DEFAULT_RENDERER_CLASSES': ['rest_framework.renderers.JSONRenderer'],
    'DEFAULT_PARSER_CLASSES': ['rest_framework.parsers.JSONParser'],
    'EXCEPTION_HANDLER': 'apps.users.errores.manejar_excepcion',
    'UNAUTHENTICATED_USER': None,
}

_ruta_privada = os.environ.get('JWT_CLAVE_PRIVADA_ARCHIVO', 'claves-dev/privada.pem')
_ruta_publica = os.environ.get('JWT_CLAVE_PUBLICA_ARCHIVO', 'claves-dev/publica.pem')

JWT_CLAVE_PRIVADA = (
    (BASE_DIR / _ruta_privada).read_text(encoding='utf-8')
    if _ruta_privada and (BASE_DIR / _ruta_privada).exists()
    else ''
)
JWT_CLAVE_PUBLICA = (
    (BASE_DIR / _ruta_publica).read_text(encoding='utf-8')
    if _ruta_publica and (BASE_DIR / _ruta_publica).exists()
    else ''
)
