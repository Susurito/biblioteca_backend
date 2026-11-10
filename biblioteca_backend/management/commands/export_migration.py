import hashlib
import json
import os
from datetime import datetime
from pathlib import Path
from django.core.management.base import BaseCommand
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.contrib.auth.models import User, Group
from biblioteca_backend.models import Alumnos, Administradores, Libros, Prestamos

class LosslessJSONEncoder(DjangoJSONEncoder):
    """Django's default encoder truncates datetime microseconds to milliseconds."""
    def default(self, value):
        if isinstance(value, datetime):
            return value.isoformat(timespec='microseconds')
        return super().default(value)


class Command(BaseCommand):
    help = 'Export a consistent snapshot after externally pausing ALL writes. Includes password hashes.'
    def add_arguments(self, parser):
        parser.add_argument('--output', required=True)
    @transaction.atomic
    def handle(self, *args, **options):
        rows = lambda model: list(model.objects.order_by('pk').values())
        payload = {name:rows(model) for name,model in [
            ('users',User),('alumnos',Alumnos),('administradores',Administradores),
            ('libros',Libros),('prestamos',Prestamos)]}
        for row in payload['users']:
            row['groups'] = list(Group.objects.filter(user=row['id']).order_by('name').values_list('name',flat=True))
        # Existing tokens survive centralization; subsequent changes belong only to identity.
        from rest_framework.authtoken.models import Token
        payload['tokens'] = list(Token.objects.order_by('user_id').values('key','user_id','created'))
        encoded = json.dumps(payload, cls=LosslessJSONEncoder, sort_keys=True, separators=(',',':'))
        snapshot = {'version':1, 'sha256':hashlib.sha256(encoded.encode()).hexdigest(), 'data':json.loads(encoded)}
        path = Path(options['output'])
        path.parent.mkdir(parents=True,exist_ok=True)
        # Refuse overwrite of an existing backup.
        fd = os.open(str(path),os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'w') as output:
            json.dump(snapshot,output)
        self.stdout.write('Snapshot exportado. Conserva este archivo fuera de Git e imágenes Docker.')
