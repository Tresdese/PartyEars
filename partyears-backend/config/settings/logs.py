from .base import *
from .base import INSTALLED_APPS, database
import os

INSTALLED_APPS = INSTALLED_APPS + ['apps.logs']

DATABASES = database('logs')

RABBITMQ_URL = os.environ.get('LOGS_RABBITMQ_URL', '')
