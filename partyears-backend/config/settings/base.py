"""
Configuración común a todos los servicios de PartyEars.

Cada servicio tiene su propio módulo (auth.py, music.py, ...) que importa
este archivo, agrega su app y apunta a su propia base de datos. Se elige con:

    DJANGO_SETTINGS_MODULE=config.settings.<servicio> python manage.py ...
"""

import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent.parent


# shortcut: no soporta comillas ni escapes en .env; usar python-dotenv si se necesitan.
def _load_env(path):
    if not path.exists():
        return
    for line in path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            key, value = line.split('=', 1)
            os.environ.setdefault(key.strip(), value.strip())


_load_env(BASE_DIR / '.env')


def env(name):
    try:
        return os.environ[name]
    except KeyError:
        raise ImproperlyConfigured(f'Falta la variable {name} en .env (ver .env.example).')


def database(service):
    """Base y rol propios del servicio; cada base vive en su propio contenedor (ver DECISIONES.md)."""
    return {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': f'partyears_{service}',
            'USER': f'{service}_svc',
            'PASSWORD': env(f'{service.upper()}_DB_PASSWORD'),
            'HOST': env('DB_HOST'),
            'PORT': env(f'{service.upper()}_DB_PORT'),
        }
    }


# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'django-insecure-sh=wos8z2mwc1ivff@^@$e*p=_!!i^t5r$7$tu(2ymu^pyj=s2'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = []


# Sin admin ni sesiones: solo el servicio auth los usa (ver auth.py).
# django.contrib.auth se queda en todos porque DRF lo necesita para AnonymousUser.
INSTALLED_APPS = [
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.staticfiles',
    'rest_framework',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'


AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


STATIC_URL = 'static/'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
