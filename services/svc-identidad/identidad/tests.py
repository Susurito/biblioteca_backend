from unittest.mock import patch
from django.test import TestCase, override_settings
from django.contrib.auth.models import User, Group
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient
from biblioteca_common.http import DependencyUnavailable
from .models import Alumnos

@override_settings(INTERNAL_SERVICE_KEY='test-key')
class IdentityTests(TestCase):
    def setUp(self):
        self.user=User.objects.create_user('ana@example.com','ana@example.com',' secret ')
        self.user.groups.add(Group.objects.create(name='alumno'))
        self.alumno=Alumnos.objects.create(user=self.user,matricula='123',nombre='Ana',apellido_paterno='Pérez',apellido_materno='')
        self.client=APIClient()
    def test_login_validate_and_logout_without_password_replication(self):
        result=self.client.post('/token/',{'username':'123','password':' secret '},format='json')
        self.assertEqual(result.status_code,200)
        self.assertEqual(result.data['alumno_id'],self.alumno.pk)
        token=result.data['token']
        self.client.credentials(HTTP_AUTHORIZATION='Token '+token)
        self.assertEqual(self.client.get('/internal/validate/').status_code,403)
        self.assertEqual(self.client.get('/internal/validate/',HTTP_X_SERVICE_KEY='test-key').status_code,200)
        self.assertEqual(self.client.post('/logout/').status_code,200)
        self.assertEqual(self.client.get('/internal/validate/',HTTP_X_SERVICE_KEY='test-key').status_code,401)
    def test_deactivated_user_is_rejected(self):
        self.user.is_active=False
        self.user.save()
        self.assertEqual(self.client.post('/token/',{'username':self.user.username,'password':' secret '}).status_code,403)
    def test_student_cannot_create_admin_or_list_students(self):
        self.client.force_authenticate(self.user)
        self.assertEqual(self.client.post('/admin/create/',{},format='json').status_code,403)
        self.assertEqual(self.client.get('/alumnos/all/').status_code,403)
    def test_missing_loan_service_never_reports_false_unblocked(self):
        self.client.force_authenticate(self.user)
        with patch('identidad.users.call',side_effect=DependencyUnavailable()):
            result=self.client.get('/perfil/')
        self.assertEqual(result.status_code,503)
        self.assertNotIn('bloqueado',result.data)
    def test_profile_distinguishes_user_and_student_ids(self):
        self.client.force_authenticate(self.user)
        summary={'bloqueado':True,'bloqueo_motivo':'RN-04','bloqueo_hasta':None,
                 'prestamos_activos':1,'limite_prestamos':3,'multas_pendientes':50,'historial_prestamos':[]}
        with patch('identidad.users.call',return_value={str(self.alumno.pk):summary}):
            result=self.client.get('/perfil/')
        self.assertEqual(result.data['user_id'],self.user.pk)
        self.assertEqual(result.data['alumno_id'],self.alumno.pk)
        self.assertTrue(result.data['bloqueado'])

from biblioteca_common.import_test_support import SnapshotImportMixin
class SnapshotTests(SnapshotImportMixin, TestCase):
    pass
