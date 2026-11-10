import uuid
from datetime import timedelta
from unittest.mock import patch
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework.exceptions import ValidationError
from biblioteca_common.auth import Principal
from biblioteca_common.http import DependencyUnavailable
from biblioteca_common.messaging import process
from .models import Prestamo, Saga, Outbox, Inbox
from .domain import approve, return_loan, reject, recover
from .rules import blocking, fine

@override_settings(INTERNAL_SERVICE_KEY='test-key')
class LoanTests(TestCase):
    def setUp(self):
        self.p=Prestamo.objects.create(alumno_id=11,user_id=5,libro_id=1,
            alumno_snapshot={'nombre':'Ana','nombre_completo':'Ana Pérez'},libro_snapshot={'titulo':'Libro'})
        self.student_patch=patch('circulacion.domain.student',return_value={'is_active':True})
        self.student_patch.start()
        self.addCleanup(self.student_patch.stop)
    def event(self,saga,kind):
        return dict(message_id=str(uuid.uuid4()),saga_id=str(saga.pk),version=1,type=kind,
                    payload={'prestamo_id':self.p.pk,'libro_id':1,'stock_total':1,'stock_disponibles':1})
    def accept(self):
        saga=approve(self.p.pk)
        process(self.event(saga,'EjemplarReservado'))
        process(self.event(saga,'ReservaConfirmada'))
        self.p.refresh_from_db()
        return saga
    def test_approval_waits_for_confirmation_and_retry_reuses_operation(self):
        saga=approve(self.p.pk)
        self.assertEqual(approve(self.p.pk).pk,saga.pk)
        self.assertEqual(Outbox.objects.count(),1)
        process(self.event(saga,'EjemplarReservado'))
        self.p.refresh_from_db()
        self.assertEqual(self.p.estado,'pendiente')
        process(self.event(saga,'ReservaConfirmada'))
        self.p.refresh_from_db()
        self.assertEqual(self.p.estado,'aceptado')
        self.assertEqual(self.p.fecha_vencimiento-self.p.fecha_solicitud,timedelta(days=7))
    def test_three_slots_include_pending_sagas(self):
        approve(self.p.pk)
        for bid in (2,3):
            p=Prestamo.objects.create(alumno_id=11,user_id=5,libro_id=bid)
            approve(p.pk)
        p=Prestamo.objects.create(alumno_id=11,user_id=5,libro_id=4)
        with self.assertRaises(ValidationError):
            approve(p.pk)
    def test_unavailable_identity_does_not_consume_event(self):
        saga=approve(self.p.pk)
        event=self.event(saga,'EjemplarReservado')
        with patch('circulacion.domain.student',side_effect=DependencyUnavailable()):
            with self.assertRaises(DependencyUnavailable):
                process(event)
        self.assertFalse(Inbox.objects.filter(pk=event['message_id']).exists())
        saga.refresh_from_db()
        self.assertEqual(saga.estado,'reservando')
    def test_deactivation_compensates_and_late_confirmation_is_ignored(self):
        saga=approve(self.p.pk)
        process(self.event(saga,'EjemplarReservado'))
        with patch('circulacion.domain.student',side_effect=ValidationError('Inactivo')):
            process(self.event(saga,'ReservaConfirmada'))
        saga.refresh_from_db()
        self.assertEqual(saga.estado,'compensando')
        process(self.event(saga,'ReservaLiberada'))
        process(self.event(saga,'ReservaConfirmada'))
        self.p.refresh_from_db()
        self.assertEqual(self.p.estado,'rechazado')
    def test_cancel_during_approval_compensates(self):
        saga=approve(self.p.pk)
        reject(self.p.pk)
        process(self.event(saga,'ReservaConfirmada'))
        self.p.refresh_from_db()
        self.assertEqual(self.p.estado,'pendiente')
        process(self.event(saga,'ReservaLiberada'))
        self.p.refresh_from_db()
        self.assertEqual(self.p.estado,'rechazado')
    def test_return_is_once_and_rn04_remains_after_payment(self):
        self.accept()
        self.p.fecha_vencimiento=timezone.now()-timedelta(days=10)
        self.p.save()
        saga=return_loan(self.p.pk)
        self.assertEqual(return_loan(self.p.pk).pk,saga.pk)
        msg=self.event(saga,'ReservaLiberada')
        process(msg)
        process(msg)
        self.p.refresh_from_db()
        self.assertEqual(fine(self.p),50)
        self.assertTrue(blocking([self.p])[0])
        client=APIClient()
        result=client.post('/internal/pagar-multa/',{'alumno_id':11},format='json',HTTP_X_SERVICE_KEY='test-key')
        self.assertEqual(result.status_code,200)
        self.assertEqual(result.data['total_pagado'],'$50.00 MXN')
        result=client.post('/internal/pagar-multa/',{'alumno_id':11},format='json',HTTP_X_SERVICE_KEY='test-key')
        self.assertEqual(result.data['total_pagado'],'$0.00 MXN')
        self.p.refresh_from_db()
        self.assertTrue(blocking([self.p])[0])
    def test_rule_boundaries(self):
        self.p.estado='aceptado'
        self.p.devuelto=True
        now=timezone.now()
        for days in (0,1,7,8):
            self.p.fecha_devolucion=now
            self.p.fecha_vencimiento=now-timedelta(days=days)
            self.assertEqual(fine(self.p),days*5)
            self.assertEqual(blocking([self.p],now)[0],days>7)
        self.assertFalse(blocking([self.p],now+timedelta(days=15))[0])
    def test_recovery_reissues_same_saga_not_new_operation(self):
        saga=approve(self.p.pk)
        Saga.objects.filter(pk=saga.pk).update(actualizado=timezone.now()-timedelta(minutes=2))
        recover(timezone.now()-timedelta(minutes=1))
        self.assertEqual(Saga.objects.count(),1)
        self.assertEqual(Outbox.objects.count(),2)
    def test_students_cannot_approve_return_or_read_other_operation(self):
        saga=approve(self.p.pk)
        c=APIClient()
        c.force_authenticate(Principal(5,'student','alumno',11))
        self.assertEqual(c.post(f'/prestamos/{self.p.pk}/aprobar/').status_code,403)
        self.assertEqual(c.patch(f'/prestamos/{self.p.pk}/',{'devuelto':True},format='json').status_code,403)
        c.force_authenticate(Principal(9,'other','alumno',20))
        self.assertEqual(c.get(f'/operaciones/{saga.pk}/').status_code,403)
    def test_api_reports_202_and_admin_cannot_bypass_state_with_put(self):
        c=APIClient()
        c.force_authenticate(Principal(1,'admin','administrador'))
        response=c.post(f'/prestamos/{self.p.pk}/aprobar/')
        self.assertEqual(response.status_code,202)
        self.assertIn('operacion_id',response.data)
        self.assertEqual(c.put(f'/prestamos/{self.p.pk}/',{'estado':'aceptado'},format='json').status_code,405)

from biblioteca_common.import_test_support import SnapshotImportMixin
class SnapshotTests(SnapshotImportMixin, TestCase):
    pass

class MessagingFailureTests(TestCase):
    def setUp(self):
        self.message=dict(message_id=str(uuid.uuid4()),saga_id=str(uuid.uuid4()),version=1,type='Unknown',
                          payload={'prestamo_id':1,'libro_id':1})
    def test_outbox_publication_failure_retains_the_message(self):
        from biblioteca_common.messaging import emit,flush
        row=emit('catalogo','ReservarEjemplar',self.message['saga_id'],self.message['payload'])
        with patch('biblioteca_common.messaging.publish',side_effect=OSError('broker down')):
            flush(object())
        row.refresh_from_db()
        self.assertIsNone(row.published_at)
        self.assertEqual(row.attempts,1)
        self.assertGreater(row.next_attempt_at,timezone.now())
    def test_retry_acknowledges_only_after_confirmed_republish(self):
        import json
        from types import SimpleNamespace
        from unittest.mock import Mock
        from biblioteca_common.messaging import consume
        channel=Mock()
        method=SimpleNamespace(delivery_tag=7)
        properties=SimpleNamespace(headers={})
        with patch('biblioteca_common.messaging.process',side_effect=ValueError('bad event')):
            with patch('biblioteca_common.messaging.publish') as publish:
                consume(channel,method,properties,json.dumps(self.message).encode())
        publish.assert_called_once()
        self.assertEqual(publish.call_args[0][1],'circulacion.retry.1')
        channel.basic_ack.assert_called_once_with(delivery_tag=7)
    def test_retry_publication_failure_nacks_original(self):
        import json
        from types import SimpleNamespace
        from unittest.mock import Mock
        from biblioteca_common.messaging import consume
        channel=Mock()
        with patch('biblioteca_common.messaging.process',side_effect=ValueError('bad event')):
            with patch('biblioteca_common.messaging.publish',side_effect=OSError('broker down')):
                with self.assertRaises(OSError):
                    consume(channel,SimpleNamespace(delivery_tag=7),SimpleNamespace(headers={}),json.dumps(self.message).encode())
        channel.basic_ack.assert_not_called()
        channel.basic_nack.assert_called_once_with(delivery_tag=7,requeue=True)
    def test_poison_message_is_persisted_and_dead_lettered(self):
        import json
        from types import SimpleNamespace
        from unittest.mock import Mock
        from biblioteca_common.messaging import consume
        from .models import FailedMessage
        channel=Mock()
        with patch('biblioteca_common.messaging.process',side_effect=ValueError('bad event')):
            with patch('biblioteca_common.messaging.publish') as publish:
                consume(channel,SimpleNamespace(delivery_tag=7),SimpleNamespace(headers={'attempt':5}),json.dumps(self.message).encode())
        self.assertEqual(FailedMessage.objects.count(),1)
        self.assertEqual(publish.call_args[0][1],'circulacion.failed')
        channel.basic_ack.assert_called_once()

class BusinessCalendarTests(TestCase):
    def test_fines_preserve_legacy_utc_days_across_mexico_midnight(self):
        from types import SimpleNamespace
        from django.utils.dateparse import parse_datetime
        from .rules import late_days, fine
        loan=SimpleNamespace(fecha_vencimiento=parse_datetime('2026-11-01T04:00:00Z'),
                             fecha_devolucion=parse_datetime('2026-11-02T08:00:00Z'))
        self.assertEqual(late_days(loan),1)
        self.assertEqual(fine(loan),5)
