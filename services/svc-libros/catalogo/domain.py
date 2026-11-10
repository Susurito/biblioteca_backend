from django.db import transaction
from django.db.models import Count, Q
from biblioteca_common.messaging import emit
from .models import Libro, Reserva


def occupied(book):
    return Reserva.objects.filter(libro=book, estado__in=['reservada','confirmada']).count()


def handle(message, publish=True):
    # The worker wraps this handler, inbox and outgoing events in one transaction.
    kind, payload = message['type'], message['payload']
    pid, bid = int(payload['prestamo_id']), int(payload['libro_id'])
    sid = message['saga_id']
    # Lock the book before the reservation on every path to serialize its last copy.
    book = Libro.objects.select_for_update().filter(pk=bid).first()
    reservation = Reserva.objects.select_for_update().filter(pk=pid).first()
    if reservation and (str(reservation.saga_id) != payload.get('reserva_saga_id', sid) or (reservation.libro_id and reservation.libro_id != bid)):
        raise ValueError('Reserva pertenece a otra Saga/libro.')
    result = None
    if kind == 'ReservarEjemplar':
        if reservation:
            result = 'EjemplarReservado' if reservation.estado in ('reservada','confirmada') else 'ReservaRechazada'
        elif book and not book.baja and occupied(book) < book.total_ejemplares:
            Reserva.objects.create(prestamo_id=pid, libro=book, saga_id=payload.get('reserva_saga_id', sid), estado='reservada')
            result = 'EjemplarReservado'
        else:
            Reserva.objects.create(prestamo_id=pid, libro=book, saga_id=payload.get('reserva_saga_id', sid), estado='rechazada')
            result = 'ReservaRechazada'
    elif kind == 'ConfirmarReserva':
        if reservation and reservation.estado in ('reservada','confirmada'):
            reservation.estado = 'confirmada'
            reservation.save(update_fields=['estado','actualizado'])
            result = 'ReservaConfirmada'
        else:
            result = 'ConfirmacionRechazada'
    elif kind == 'LiberarReserva':
        if not reservation:
            # Tombstone prevents a delayed reservation command from allocating stock.
            reservation = Reserva.objects.create(prestamo_id=pid, libro=book, saga_id=payload.get('reserva_saga_id', sid), estado='liberada')
        else:
            reservation.estado = 'liberada'
            reservation.save(update_fields=['estado','actualizado'])
        result = 'ReservaLiberada'
    else:
        raise ValueError('Comando desconocido: '+kind)
    response = dict(payload, motivo='Sin existencias o libro dado de baja.' if result == 'ReservaRechazada' else '',
         stock_total=book.total_ejemplares if book else 0,
         stock_disponibles=max(0, book.total_ejemplares-occupied(book)) if book else 0)
    if publish:
        emit('circulacion', result, sid, response)
    return {'type': result, 'payload': response}
