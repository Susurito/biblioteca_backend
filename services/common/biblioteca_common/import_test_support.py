import hashlib
import json
import tempfile
from pathlib import Path
from io import StringIO
from django.core.management import call_command
from django.core.management.base import CommandError
from django.conf import settings
from django.contrib.auth.hashers import make_password
from biblioteca_common.migration import expected

class SnapshotImportMixin:
    def snapshot(self):
        data={
          'users':[dict(id=501,username='ana@example.com',email='ana@example.com',password=make_password('password'),
            first_name='Ana',last_name='Pérez',is_active=True,is_superuser=False,is_staff=False,
            last_login=None,date_joined='2026-10-01T12:00:00.123456Z',groups=['alumno'])],
          'alumnos':[dict(id=9001,user_id=501,matricula='1234567890',nombre='Ana',apellido_paterno='Pérez',apellido_materno='',rol='Estudiante',
            creado='2026-10-01T12:00:00.123456Z',actualizado='2026-10-01T12:00:00.123456Z')],
          'administradores':[],
          'libros':[dict(id=8001,isbn=None,titulo='Libro',autor='Autor',genero='Software',detalles='',total_ejemplares=1,baja=False,disponible=False,
            creado='2026-10-01T12:00:00.123456Z',actualizado='2026-10-01T12:00:00.123456Z')],
          'prestamos':[dict(id=7001,alumno_id=9001,libro_id=8001,fecha_solicitud='2026-10-01T12:00:00.123456Z',
            fecha_vencimiento='2026-10-08T12:00:00.654321Z',fecha_devolucion=None,devuelto=False,estado='aceptado',multa_pagada=False,fecha_pago_multa=None)],
          'tokens':[dict(key='a'*40,user_id=501,created='2026-10-01T12:00:00.123456Z')]
        }
        text=json.dumps(data,sort_keys=True,separators=(',',':'))
        return {'version':1,'sha256':hashlib.sha256(text.encode()).hexdigest(),'data':data}
    def test_snapshot_import_verify_and_refuse_overwrite(self):
        snapshot=self.snapshot()
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'snapshot.json'
            path.write_text(json.dumps(snapshot))
            call_command('import_snapshot',str(path),stdout=StringIO())
            call_command('import_snapshot',str(path),verify_only=True,stdout=StringIO())
            with self.assertRaises(CommandError):
                call_command('import_snapshot',str(path),stdout=StringIO())
            model,rows=expected(snapshot['data'])[0]
            pk=rows[0]['id']
            field='email' if settings.SERVICE_NAME=='identidad' else 'titulo' if settings.SERVICE_NAME=='catalogo' else 'estado'
            model.objects.filter(pk=pk).update(**{field:'changed'})
            with self.assertRaises(CommandError):
                call_command('import_snapshot',str(path),verify_only=True,stdout=StringIO())
    def test_corrupt_checksum_refused_before_any_write(self):
        snapshot=self.snapshot()
        snapshot['sha256']='invalid'
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'snapshot.json'
            path.write_text(json.dumps(snapshot))
            with self.assertRaises(CommandError):
                call_command('import_snapshot',str(path),stdout=StringIO())
