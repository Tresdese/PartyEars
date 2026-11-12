from django.conf import settings
from django.urls import path

urlpatterns = []

if 'django.contrib.admin' in settings.INSTALLED_APPS:
    from django.contrib import admin

    urlpatterns.append(path('admin/', admin.site.urls))
