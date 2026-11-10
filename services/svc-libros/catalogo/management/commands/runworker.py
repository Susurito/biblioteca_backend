from django.core.management.base import BaseCommand
from biblioteca_common.messaging import run
class Command(BaseCommand):
    help = 'Consume RabbitMQ, publish transactional outbox and recover pending Sagas.'
    def handle(self, *args, **options):
        run()
