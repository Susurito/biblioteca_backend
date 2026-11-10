from unittest.mock import patch
from django.test import TestCase,override_settings
from django.contrib.auth.models import User,Group
from rest_framework.test import APIClient
from biblioteca_common.auth import Principal
from biblioteca_backend.models import Alumnos,Libros,Prestamos
from biblioteca_backend.migration_bridge import legacy_action,IdentityAuthentication

@override_settings(INTERNAL_SERVICE_KEY='test-key')
class LegacyBridgeTests(TestCase):
    def setUp(self):
        self.user=User.objects.create_user('ana@example.com','ana@example.com','password')
        self.user.groups.add(Group.objects.create(name='alumno'))
        self.a=Alumnos.objects.create(user=self.user,matricula='12',nombre='Ana',apellido_paterno='P',apellido_materno='')
        self.b=Libros.objects.create(titulo='Libro',autor='Autor',genero='Software')
        self.p=Prestamos.objects.create(alumno=self.a,libro=self.b)
    def test_service_auth_required_for_summary(self):
        client=APIClient()
        self.assertEqual(client.post('/internal/resumenes/',{'alumno_ids':[self.a.pk]},format='json').status_code,403)
        response=client.post('/internal/resumenes/',{'alumno_ids':[self.a.pk]},format='json',HTTP_X_SERVICE_KEY='test-key')
        self.assertEqual(response.status_code,200)
        self.assertFalse(response.data[str(self.a.pk)]['bloqueado'])
    def test_remote_approval_and_return_do_not_write_book_inventory(self):
        def command(loan,kind):
            return {'type': {'ReservarEjemplar':'EjemplarReservado','ConfirmarReserva':'ReservaConfirmada','LiberarReserva':'ReservaLiberada'}[kind], 'payload':{'stock_total':1,'stock_disponibles':1}}
        with patch('biblioteca_backend.migration_bridge.catalog_command',side_effect=command):
            legacy_action(self.p.pk,'aprobar')
            legacy_action(self.p.pk,'aprobar')
            result=legacy_action(self.p.pk,'devolver')
            self.assertEqual(result['detalles_devolucion']['stock_disponibles'],1)
            legacy_action(self.p.pk,'devolver')
        self.p.refresh_from_db(); self.b.refresh_from_db()
        self.assertTrue(self.p.devuelto)
        self.assertTrue(self.b.disponible)
        self.assertEqual(self.b.total_ejemplares,1)
    def test_identity_projection_does_not_replicate_password(self):
        data=dict(username=self.user.username,email=self.user.email,nombre='Ana',apellido_paterno='P',apellido_materno='',
                  is_active=True,alumno_id=self.a.pk,matricula='12',rol='alumno')
        with patch('biblioteca_common.auth.RemoteTokenAuthentication.authenticate',return_value=(Principal(self.user.pk,self.user.username,'alumno',self.a.pk),'opaque')):
            with patch('biblioteca_backend.migration_bridge.call',return_value=data):
                user,token=IdentityAuthentication().authenticate(object())
        self.assertFalse(user.has_usable_password())

    def test_export_snapshot_preserves_credentials_ids_and_references(self):
        import tempfile
        from pathlib import Path
        from io import StringIO
        from django.core.management import call_command
        from biblioteca_common.migration import load_snapshot
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'snapshot.json'
            call_command('export_migration',output=str(path),stdout=StringIO())
            data=load_snapshot(str(path))
            self.assertEqual(data['users'][0]['id'],self.user.pk)
            self.assertEqual(data['users'][0]['password'],self.user.password)
            from django.utils.dateparse import parse_datetime
            self.user.refresh_from_db()
            self.p.refresh_from_db()
            self.assertEqual(parse_datetime(data['users'][0]['date_joined']), self.user.date_joined)
            self.assertEqual(parse_datetime(data['prestamos'][0]['fecha_solicitud']), self.p.fecha_solicitud)
            self.assertEqual(data['prestamos'][0]['alumno_id'],self.a.pk)
            self.assertEqual(path.stat().st_mode & 0o777,0o600)

    def test_legacy_create_cannot_bypass_request_validation(self):
        client=APIClient()
        client.force_authenticate(self.user)
        book=Libros.objects.create(titulo='Otro',autor='Autor',genero='Software')
        response=client.post('/prestamos/',{'libro':book.pk,'estado':'aceptado','devuelto':True},format='json')
        self.assertEqual(response.status_code,201,response.data)
        created=Prestamos.objects.get(pk=response.data['id'])
        self.assertEqual(created.alumno_id,self.a.pk)
        self.assertEqual(created.estado,'pendiente')
        self.assertFalse(created.devuelto)
        self.assertEqual(client.post('/prestamos/',{'libro':book.pk},format='json').status_code,400)
        self.assertEqual(client.post('/admin/create/',{},format='json').status_code,403)
