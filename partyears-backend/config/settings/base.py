import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent.parent


# Own loader instead of python-dotenv to avoid a dependency for a few lines.
# shortcut: no quotes or escapes supported in .env; switch to python-dotenv if needed.
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
    # Dev uses a personal account instead of the <service>_svc password: the server switches
    # to the service role on connect, so table ownership matches production.
    if os.environ.get('DB_USER'):
        user, password = os.environ['DB_USER'], env('DB_PASSWORD')
    else:
        user, password = f'{service}_svc', env(f'{service.upper()}_DB_PASSWORD')
    return {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': f'partyears_{service}',
            'USER': user,
            'PASSWORD': password,
            'HOST': env('DB_HOST'),
            'PORT': env(f'{service.upper()}_DB_PORT'),
        }
    }


SECRET_KEY = 'django-insecure-sh=wos8z2mwc1ivff@^@$e*p=_!!i^t5r$7$tu(2ymu^pyj=s2'

DEBUG = True

ALLOWED_HOSTS = []


# No admin or sessions here: only the auth service uses them (see auth.py).
# django.contrib.auth stays in every service because DRF needs it for AnonymousUser.
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
