from django.conf import settings
from django.urls import include, path

urlpatterns = []

if 'django.contrib.admin' in settings.INSTALLED_APPS:
    from django.contrib import admin

    urlpatterns.append(path('admin/', admin.site.urls))

if 'apps.users' in settings.INSTALLED_APPS:
    urlpatterns.append(path('', include('apps.users.urls')))

if 'apps.parties' in settings.INSTALLED_APPS:
    urlpatterns.append(path('', include('apps.parties.urls')))

if 'apps.musicqueue' in settings.INSTALLED_APPS:
    urlpatterns.append(path('', include('apps.musicqueue.urls')))
