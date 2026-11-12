from .base import *
from .base import INSTALLED_APPS, database

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
