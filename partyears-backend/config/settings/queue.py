from .base import *  # noqa: F401,F403
from .base import INSTALLED_APPS, database

INSTALLED_APPS = INSTALLED_APPS + ['apps.musicqueue']

DATABASES = database('queue')
