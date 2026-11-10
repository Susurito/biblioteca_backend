from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from biblioteca_common.messaging import model, validate
class Command(BaseCommand):
    help = 'Replay a failed message into the local queue through the outbox.'
    def add_arguments(self, parser):
        parser.add_argument('message_id')
    @transaction.atomic
    def handle(self, *args, **options):
        row = model('FailedMessage').objects.select_for_update().get(pk=options['message_id'])
        validate(row.body)
        if row.replayed_at:
            raise CommandError('El mensaje ya fue reenviado.')
        # The original failed processing rolled back its inbox transaction.
        mid = __import__('uuid').uuid4()
        from django.conf import settings
        model('Outbox').objects.create(id=mid, routing_key=settings.SERVICE_NAME+'.'+row.body['type'], body=row.body)
        row.replayed_at = timezone.now()
        row.save(update_fields=['replayed_at'])
        self.stdout.write('Reenvío registrado en outbox.')
