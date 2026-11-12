from .base import *
from .base import INSTALLED_APPS, database

INSTALLED_APPS = INSTALLED_APPS + ['apps.music']

DATABASES = database('music')
