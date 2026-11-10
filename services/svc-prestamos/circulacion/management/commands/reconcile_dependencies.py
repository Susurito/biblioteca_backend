from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from biblioteca_common.http import call
from circulacion.models import Prestamo

class Command(BaseCommand):
    help='Read-only reconciliation of references and active physical allocations before cutover.'
    def handle(self,*args,**options):
        loans=list(Prestamo.objects.all())
        ids=sorted({p.alumno_id for p in loans})
        students={}
        for i in range(0,len(ids),1000):
            students.update(call(settings.IDENTITY_URL,'/internal/alumnos/',{'alumno_ids':ids[i:i+1000]}))
        ids=sorted({p.libro_id for p in loans})
        books={}
        for i in range(0,len(ids),1000):
            books.update(call(settings.BOOKS_URL,'/internal/libros/',{'libro_ids':ids[i:i+1000]}))
        for p in loans:
            if str(p.alumno_id) not in students or students[str(p.alumno_id)]['user_id']!=p.user_id:
                raise CommandError('Referencia de alumno/usuario inválida en préstamo '+str(p.pk))
            if str(p.libro_id) not in books:
                raise CommandError('Referencia de libro inválida en préstamo '+str(p.pk))
        remote=call(settings.BOOKS_URL,'/internal/asignaciones/')
        if any(row['estado']!='confirmada' for row in remote):
            raise CommandError('Hay reservas sin confirmar. Drenar antes de cambiar tráfico.')
        expected={(p.pk,p.libro_id) for p in loans if p.estado=='aceptado' and not p.devuelto}
        actual={(row['prestamo_id'],row['libro_id']) for row in remote}
        if expected!=actual:
            raise CommandError(f'Asignaciones distintas: faltantes={sorted(expected-actual)}, extras={sorted(actual-expected)}')
        self.stdout.write('Conciliación entre servicios correcta: referencias y asignaciones activas.')
