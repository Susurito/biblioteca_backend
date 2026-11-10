import uuid
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from biblioteca_common.auth import Principal
from biblioteca_common.messaging import process
from .models import Libro, Reserva, Outbox, Inbox

@override_settings(INTERNAL_SERVICE_KEY='test-key')
class CatalogTests(TestCase):
    def setUp(self):
        self.book=Libro.objects.create(titulo='Arquitectura',autor='Autor',genero='Software',total_ejemplares=1)
        self.sid=str(uuid.uuid4())
    def message(self,kind,pid=1,sid=None):
        return dict(message_id=str(uuid.uuid4()),saga_id=sid or self.sid,version=1,type=kind,
                    payload={'prestamo_id':pid,'libro_id':self.book.pk})
    def test_last_copy_and_duplicate_delivery(self):
        msg=self.message('ReservarEjemplar')
        self.assertTrue(process(msg))
        self.assertFalse(process(msg))
        process(self.message('ReservarEjemplar',2,str(uuid.uuid4())))
        self.assertEqual(Reserva.objects.get(pk=1).estado,'reservada')
        self.assertEqual(Reserva.objects.get(pk=2).estado,'rechazada')
        self.assertEqual(Outbox.objects.count(),2)
    def test_release_before_reserve_creates_terminal_tombstone(self):
        process(self.message('LiberarReserva'))
        process(self.message('ReservarEjemplar'))
        process(self.message('ConfirmarReserva'))
        self.assertEqual(Reserva.objects.get(pk=1).estado,'liberada')
        self.assertEqual(Outbox.objects.order_by('created_at').last().body['type'],'ConfirmacionRechazada')
    def test_confirm_and_release_are_idempotent_with_new_message_ids(self):
        for kind in ['ReservarEjemplar','ConfirmarReserva','ConfirmarReserva','LiberarReserva','LiberarReserva']:
            process(self.message(kind))
        self.assertEqual(Reserva.objects.get(pk=1).estado,'liberada')
    def test_failed_processing_rolls_back_inbox_and_outbox(self):
        msg=self.message('InvalidCommand')
        with self.assertRaises(ValueError):
            process(msg)
        self.assertFalse(Inbox.objects.filter(pk=msg['message_id']).exists())
        self.assertEqual(Outbox.objects.count(),0)
    def test_return_uses_original_allocation_saga(self):
        process(self.message('ReservarEjemplar'))
        msg=self.message('LiberarReserva',sid=str(uuid.uuid4()))
        msg['payload']['reserva_saga_id']=self.sid
        process(msg)
        self.assertEqual(Reserva.objects.get(pk=1).estado,'liberada')
    def test_admin_permissions_and_inventory_changes(self):
        c=APIClient()
        c.force_authenticate(Principal(1,'student','alumno',1))
        self.assertEqual(c.post('/libros/',{},format='json').status_code,403)
        c.force_authenticate(Principal(2,'admin','administrador'))
        process(self.message('ReservarEjemplar'))
        self.assertEqual(c.post(f'/libros/{self.book.pk}/dar-de-baja/').status_code,400)
        self.assertEqual(c.patch(f'/libros/{self.book.pk}/',{'total_ejemplares':0},format='json').status_code,400)
    def test_internal_endpoints_require_service_key(self):
        c=APIClient()
        self.assertEqual(c.post('/internal/libros/',{'libro_ids':[self.book.pk]},format='json').status_code,403)
        self.assertEqual(c.post('/internal/libros/',{'libro_ids':[self.book.pk]},format='json',HTTP_X_SERVICE_KEY='test-key').status_code,200)

from biblioteca_common.import_test_support import SnapshotImportMixin
class SnapshotTests(SnapshotImportMixin, TestCase):
    pass
