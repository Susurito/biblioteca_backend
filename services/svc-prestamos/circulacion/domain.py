from datetime import timedelta
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from biblioteca_common.http import call
from biblioteca_common.messaging import emit
from .models import Prestamo, Saga, AlumnoLock
from .rules import blocking, late_days, fine

TERMINAL = ('completada', 'fallida')


def lock_student(aid):
    AlumnoLock.objects.get_or_create(alumno_id=aid)
    return AlumnoLock.objects.select_for_update().get(pk=aid)


def eligibility(aid):
    rows = list(Prestamo.objects.filter(alumno_id=aid))
    blocked, reason, until = blocking(rows)
    if blocked:
        raise ValidationError({'error': reason, 'bloqueado': True, 'fecha_desbloqueo': until})
    active = sum(p.estado=='aceptado' and not p.devuelto for p in rows)
    running = Saga.objects.filter(prestamo__alumno_id=aid, tipo='aprobar',
                                  estado__in=['reservando','confirmando','compensando']).count()
    if active + running >= 3:
        raise ValidationError({'error': 'Límite de tres préstamos, incluyendo aprobaciones en curso.'})


def student(aid):
    data = call(settings.IDENTITY_URL, '/internal/alumnos/', {'alumno_ids':[aid]}).get(str(aid))
    if not data or not data['is_active']:
        raise ValidationError({'error': 'Alumno inexistente o inactivo.'})
    return data


def send(saga, kind):
    loan = saga.prestamo
    original = Saga.objects.filter(prestamo=loan, tipo='aprobar').first()
    emit('catalogo', kind, str(saga.pk), {'prestamo_id':loan.pk, 'libro_id':loan.libro_id,
         'reserva_saga_id': str(original.pk) if original else str(saga.pk)})


@transaction.atomic
def approve(pid):
    preview = Prestamo.objects.get(pk=pid)
    lock_student(preview.alumno_id)
    loan = Prestamo.objects.select_for_update().get(pk=pid)
    existing = Saga.objects.filter(prestamo=loan, tipo='aprobar').first()
    if existing:
        return existing
    if loan.estado != 'pendiente' or loan.devuelto:
        raise ValidationError({'error':'Solo se aprueban solicitudes pendientes.'})
    student(loan.alumno_id)
    eligibility(loan.alumno_id)
    saga = Saga.objects.create(prestamo=loan, tipo='aprobar', estado='reservando')
    send(saga, 'ReservarEjemplar')
    return saga


@transaction.atomic
def reject(pid):
    preview = Prestamo.objects.get(pk=pid)
    lock_student(preview.alumno_id)
    loan = Prestamo.objects.select_for_update().get(pk=pid)
    if loan.estado == 'aceptado' or loan.devuelto:
        raise ValidationError({'error':'No se rechaza un préstamo aprobado o devuelto.'})
    saga = Saga.objects.select_for_update().filter(prestamo=loan, tipo='aprobar').first()
    if saga and saga.estado not in TERMINAL:
        saga.estado = 'compensando'
        saga.error = 'Solicitud rechazada por administrador.'
        saga.resultado = {'rechazo_solicitado': True}
        saga.actualizado = timezone.now()
        saga.save()
        send(saga, 'LiberarReserva')
        return saga
    loan.estado = 'rechazado'
    loan.save(update_fields=['estado'])
    return None


@transaction.atomic
def return_loan(pid):
    preview = Prestamo.objects.get(pk=pid)
    lock_student(preview.alumno_id)
    loan = Prestamo.objects.select_for_update().get(pk=pid)
    existing = Saga.objects.filter(prestamo=loan, tipo='devolver').first()
    if existing:
        return existing
    if loan.estado != 'aceptado' or loan.devuelto:
        raise ValidationError({'error':'Solo se devuelven préstamos activos.'})
    loan.devuelto = True
    loan.fecha_devolucion = timezone.now()
    loan.save(update_fields=['devuelto','fecha_devolucion'])
    saga = Saga.objects.create(prestamo=loan, tipo='devolver', estado='liberando')
    send(saga, 'LiberarReserva')
    return saga


def handle(message):
    sid = message['saga_id']
    preview = Saga.objects.select_related('prestamo').get(pk=sid)
    lock_student(preview.prestamo.alumno_id)
    saga = Saga.objects.select_for_update().select_related('prestamo').get(pk=sid)
    loan = Prestamo.objects.select_for_update().get(pk=saga.prestamo_id)
    payload, kind = message['payload'], message['type']
    if int(payload['prestamo_id']) != loan.pk or int(payload['libro_id']) != loan.libro_id:
        raise ValueError('Evento no corresponde al préstamo de la Saga.')
    if saga.estado in TERMINAL:
        return
    if saga.tipo == 'aprobar':
        if kind == 'EjemplarReservado' and saga.estado == 'reservando':
            try:
                student(loan.alumno_id)
                blocked, reason, _ = blocking(Prestamo.objects.filter(alumno_id=loan.alumno_id))
                if blocked:
                    raise ValidationError(reason)
            except ValidationError as exc:
                saga.estado, saga.error = 'compensando', str(exc.detail)
                send(saga, 'LiberarReserva')
            else:
                saga.estado = 'confirmando'
                send(saga, 'ConfirmarReserva')
        elif kind == 'ReservaConfirmada' and saga.estado == 'confirmando':
            try:
                student(loan.alumno_id)
                blocked, reason, _ = blocking(Prestamo.objects.filter(alumno_id=loan.alumno_id))
                if blocked:
                    raise ValidationError(reason)
            except ValidationError as exc:
                saga.estado, saga.error = 'compensando', str(exc.detail)
                send(saga, 'LiberarReserva')
            else:
                loan.estado = 'aceptado'
                loan.fecha_solicitud = timezone.now()
                loan.fecha_vencimiento = loan.fecha_solicitud + timedelta(days=7)
                loan.save()
                saga.estado = 'completada'
                saga.resultado = {'message': 'Préstamo aprobado.', 'prestamo_id':loan.pk}
        elif kind == 'ReservaRechazada' and saga.estado == 'reservando':
            loan.estado = 'rechazado'
            loan.save(update_fields=['estado'])
            saga.estado, saga.error = 'fallida', payload.get('motivo') or 'Reserva rechazada.'
        elif kind == 'ConfirmacionRechazada' and saga.estado == 'confirmando':
            saga.estado, saga.error = 'compensando', 'No se pudo confirmar la reserva.'
            send(saga, 'LiberarReserva')
        elif kind == 'ReservaLiberada' and saga.estado == 'compensando':
            loan.estado = 'rechazado'
            loan.save(update_fields=['estado'])
            saga.estado = 'fallida'
            if saga.resultado.get('rechazo_solicitado'):
                saga.resultado = {'rechazo_confirmado': True, 'message': 'Solicitud rechazada.'}
    elif saga.tipo == 'devolver' and kind == 'ReservaLiberada' and saga.estado == 'liberando':
        saga.estado = 'completada'
        days = late_days(loan)
        end = loan.fecha_devolucion + timedelta(days=15)
        details = {
            'id': loan.id, 'alumno_nombre': loan.alumno_snapshot.get('nombre',''),
            'alumno_nombre_completo': loan.alumno_snapshot.get('nombre_completo',''),
            'libro_titulo': loan.libro_snapshot.get('titulo',''), 'libro_autor':loan.libro_snapshot.get('autor',''),
            'fecha_vencimiento':timezone.localtime(loan.fecha_vencimiento).strftime('%d/%m/%Y') if loan.fecha_vencimiento else '-',
            'fecha_devolucion':timezone.localtime(loan.fecha_devolucion).strftime('%d/%m/%Y'),
            'dias_retraso':days, 'multa':f'${fine(loan):.2f} MXN',
            'bloqueo': 'Hasta el '+timezone.localtime(end).strftime('%d/%m/%Y') if days>7 else '------',
            'mensaje_sancion': 'RN-04: multa y suspensión de 15 días.' if days>7 else 'RN-03: multa sin suspensión.' if days else 'Devolución a tiempo, sin sanción',
            'stock_total':payload['stock_total'], 'stock_disponibles':payload['stock_disponibles'],
            'stock_mensaje':f"Stock actualizado: {payload['stock_disponibles']} de {payload['stock_total']} disponibles."
        }
        saga.resultado = {'message':'Devolución registrada.', 'detalles_devolucion':details}
    saga.actualizado = timezone.now()
    saga.save()


@transaction.atomic
def recover(stale_before):
    # New message IDs allow re-delivery of an already processed command to replay its result.
    for saga in Saga.objects.select_for_update().filter(actualizado__lt=stale_before).exclude(estado__in=TERMINAL):
        command = {'reservando':'ReservarEjemplar','confirmando':'ConfirmarReserva',
                   'compensando':'LiberarReserva','liberando':'LiberarReserva'}[saga.estado]
        send(saga, command)
        saga.actualizado = timezone.now()
        saga.save(update_fields=['actualizado'])
