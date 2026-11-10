import time
import logging
from django.conf import settings
from rest_framework.exceptions import ValidationError
from django.core.management.base import BaseCommand
from biblioteca_common.http import call
from biblioteca_backend.models import Prestamos
from biblioteca_backend.migration_bridge import legacy_action, catalog_command

class Command(BaseCommand):
    help='Recover idempotent catalog allocations while the monolith owns loans.'
    def add_arguments(self,parser):
        parser.add_argument('--loop',action='store_true')
    def handle(self,*args,**options):
        while True:
            try:
                if settings.CATALOG_REMOTE_ENABLED:
                    rows=call(settings.BOOKS_URL,'/internal/legacy-reservas/')
                    for row in rows:
                        p=Prestamos.objects.filter(pk=row['prestamo_id']).first()
                        if not p:
                            # This can also mean loans have moved. Never release unknown allocations.
                            continue
                        if p.devuelto or p.estado=='rechazado':
                            catalog_command(p,'LiberarReserva')
                        elif p.estado=='pendiente':
                            try:
                                legacy_action(p.pk,'aprobar')
                            except ValidationError:
                                legacy_action(p.pk,'rechazar')
                            except Exception:
                                # Keep unresolved stock reserved; do not infer failure from timeouts.
                                logging.exception('Legacy approval pending loan_id=%s',p.pk)
            except Exception:
                logging.exception('Legacy catalog recovery failed')
                if not options['loop']:
                    raise
            if not options['loop']:
                return
            time.sleep(5)
