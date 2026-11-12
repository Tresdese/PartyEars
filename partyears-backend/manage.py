#!/usr/bin/env python
import os
import sys


def main():
    if 'DJANGO_SETTINGS_MODULE' not in os.environ:
        sys.exit('Indica el servicio, por ejemplo:\n'
                 '  DJANGO_SETTINGS_MODULE=config.settings.auth python manage.py runserver 8001')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
