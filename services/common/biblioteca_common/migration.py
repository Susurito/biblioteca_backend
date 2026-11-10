"""Explicit, offline import. This module never reads another service's database."""
import hashlib
import json
import uuid
from datetime import timedelta
from django.apps import apps
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction, connection
from django.core.management.color import no_style
from django.utils.dateparse import parse_datetime
from django.conf import settings


def legacy_saga(pid):
    return uuid.uuid5(uuid.NAMESPACE_URL, 'biblioteca:legacy-loan:'+str(pid))


def load_snapshot(path):
    with open(path) as f:
        snapshot=json.load(f)
    encoded=json.dumps(snapshot['data'],sort_keys=True,separators=(',',':'))
    if snapshot['version']!=1 or hashlib.sha256(encoded.encode()).hexdigest()!=snapshot['sha256']:
        raise CommandError('Snapshot incompatible o checksum incorrecto.')
    data=snapshot['data']
    users={u['id'] for u in data['users']}
    students={a['id'] for a in data['alumnos']}
    books={b['id'] for b in data['libros']}
    for a in data['alumnos']+data['administradores']:
        if a['user_id'] not in users:
            raise CommandError('Perfil huérfano.')
    for p in data['prestamos']:
        if p['alumno_id'] not in students or p['libro_id'] not in books:
            raise CommandError('Préstamo huérfano.')
    for token in data['tokens']:
        if token['user_id'] not in users:
            raise CommandError('Token huérfano.')
    return data


def clean(model, row):
    result={}
    for field in model._meta.fields:
        key=field.attname
        if key in row:
            value=row[key]
            result[key]=parse_datetime(value) if field.get_internal_type()=='DateTimeField' and isinstance(value,str) else value
    return result


def expected(data):
    service=settings.SERVICE_NAME
    if service=='identidad':
        from rest_framework.authtoken.models import Token
        result=[(get_user_model(),data['users']), (apps.get_model(service,'Alumnos'),data['alumnos']),
                (apps.get_model(service,'Administradores'),data['administradores']), (Token,data['tokens'])]
        return result
    if service=='catalogo':
        book=apps.get_model(service,'Libro')
        reservation=apps.get_model(service,'Reserva')
        rows=[{'prestamo_id':p['id'],'saga_id':legacy_saga(p['id']),'libro_id':p['libro_id'],'estado':'confirmada'}
              for p in data['prestamos'] if p['estado']=='aceptado' and not p['devuelto']]
        # Check inventory before switching the writer.
        from collections import Counter
        counts=Counter(row['libro_id'] for row in rows)
        for b in data['libros']:
            if counts[b['id']]>b['total_ejemplares'] or (counts[b['id']] and b['baja']):
                raise CommandError('Inventario inconsistente: libro '+str(b['id']))
        return [(book,data['libros']),(reservation,rows)]
    students={a['id']:a for a in data['alumnos']}
    books={b['id']:b for b in data['libros']}
    users={u['id']:u for u in data['users']}
    rows=[]
    for original in data['prestamos']:
        p=dict(original)
        a=students[p['alumno_id']]
        a=dict(a, nombre_completo=' '.join(a[k] for k in ('nombre','apellido_paterno','apellido_materno')).strip())
        p.update(user_id=a['user_id'],alumno_snapshot=a,libro_snapshot=books[p['libro_id']])
        rows.append(p)
    loan=apps.get_model(service,'Prestamo')
    saga=apps.get_model(service,'Saga')
    operations=[{'id':legacy_saga(p['id']), 'prestamo_id':p['id'],'tipo':'aprobar','estado':'completada',
                 'resultado':{'message':'Préstamo importado.'},'error':''}
                for p in rows if p['estado']=='aceptado']
    return [(loan,rows),(saga,operations)]


class ImportCommand(BaseCommand):
    help='Import into EMPTY domain tables, or reconcile every exported field using --verify-only.'
    def add_arguments(self,parser):
        parser.add_argument('snapshot')
        parser.add_argument('--verify-only',action='store_true')
    @transaction.atomic
    def handle(self,*args,**options):
        data=load_snapshot(options['snapshot'])
        groups=expected(data)
        if not options['verify_only']:
            if any(model.objects.exists() for model,rows in groups):
                raise CommandError('Destino no vacío. Usa --verify-only; no se sobrescriben datos.')
            for model,rows in groups:
                for row in rows:
                    values=clean(model,row)
                    obj=model.objects.create(**values)
                    # auto_now fields are assigned by save(); restore original exported timestamps.
                    model.objects.filter(pk=obj.pk).update(**values)
            if settings.SERVICE_NAME=='identidad':
                user_model=get_user_model()
                for row in data['users']:
                    user=user_model.objects.get(pk=row['id'])
                    user.groups.set([Group.objects.get_or_create(name=name)[0] for name in row['groups']])
            sql=connection.ops.sequence_reset_sql(no_style(),[m for m,_ in groups])
            with connection.cursor() as cursor:
                for statement in sql:
                    cursor.execute(statement)
        for model,rows in groups:
            if model.objects.count()!=len(rows):
                raise CommandError('Conteo distinto: '+model._meta.label)
            for row in rows:
                values=clean(model,row)
                pk=values[model._meta.pk.attname]
                obj=model.objects.get(pk=pk)
                for key,value in values.items():
                    actual=getattr(obj,key)
                    if str(actual)!=str(value) and actual!=value:
                        raise CommandError(f'Diferencia en {model._meta.label} {pk} campo {key}')
        if settings.SERVICE_NAME=='identidad':
            for row in data['users']:
                user=get_user_model().objects.get(pk=row['id'])
                if sorted(user.groups.values_list('name',flat=True))!=sorted(row['groups']):
                    raise CommandError('Grupos distintos para usuario '+str(user.pk))
        self.stdout.write('Conciliación correcta: IDs, relaciones, campos, contraseñas y conteos conservados.')
