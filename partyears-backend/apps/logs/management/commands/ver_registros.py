from django.core.management.base import BaseCommand

from apps.logs.models import EventoLog


class Command(BaseCommand):
    help = 'CU-27: consulta los registros técnicos por party, actor u operación.'

    def add_arguments(self, parser):
        parser.add_argument('--party', help='UUID de la party')
        parser.add_argument('--actor', help='UUID del usuario que hizo la operación')
        parser.add_argument('--operacion', help='Idempotency-Key de la operación')
        parser.add_argument('--desde', help='Fecha ISO, por ejemplo 2026-11-25T10:00:00-06:00')
        parser.add_argument('--limite', type=int, default=50)

    def handle(self, *args, **opciones):
        filtros = {'party_id': opciones['party'], 'actor_usuario_id': opciones['actor'],
                   'correlacion_id': opciones['operacion'], 'ocurrido_en__gte': opciones['desde']}
        registros = (EventoLog.objects.filter(**{k: v for k, v in filtros.items() if v})
                     .order_by('-ocurrido_en')[:opciones['limite']])
        for r in reversed(registros):
            self.stdout.write(f'{r.ocurrido_en.isoformat()} {r.nivel:7} {r.servicio_codigo:5} '
                              f'actor={r.actor_usuario_id} party={r.party_id} {r.mensaje}')
        if not registros:
            # CU-27 FA-01: say nothing was found instead of implying the operation succeeded.
            self.stdout.write('No hay registros con esos filtros.')
