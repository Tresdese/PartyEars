from django.core.management.base import BaseCommand

from apps.parties.servicios import cerrar_participaciones_abiertas


class Command(BaseCommand):
    help = ('Al arrancar party: marca como desconectado a quien quedó dentro cuando se apagó el '
            'backend anterior. No usar si otro proceso party usa la misma base al mismo tiempo.')

    def handle(self, *args, **opciones):
        cerradas = cerrar_participaciones_abiertas()
        self.stdout.write(f'Participaciones que quedaron abiertas y se cerraron: {cerradas}')
