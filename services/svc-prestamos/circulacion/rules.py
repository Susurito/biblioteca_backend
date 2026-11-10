from datetime import timedelta, timezone as datetime_timezone
from decimal import Decimal
from django.utils import timezone


def day(value):
    # Preserve the monolith's UTC calendar for RN-03/RN-04; display timezone is independent.
    return value.astimezone(datetime_timezone.utc).date()


def late_days(loan, at=None):
    end = loan.fecha_devolucion or at or timezone.now()
    return max(0, (day(end)-day(loan.fecha_vencimiento)).days) if loan.fecha_vencimiento else 0


def fine(loan):
    return Decimal(late_days(loan)) * Decimal('5.00')


def blocking(loans, now=None):
    now = now or timezone.now()
    untils = []
    for loan in loans:
        if loan.estado != 'aceptado' or late_days(loan, now) <= 7:
            continue
        if not loan.devuelto:
            return True, 'RN-04: devuelve el libro atrasado y cumple 15 días de suspensión.', None
        end = loan.fecha_devolucion + timedelta(days=15)
        if end > now:
            untils.append(end)
    if untils:
        end = max(untils)
        return True, 'RN-04: suspensión de 15 días después de la devolución.', day(end).strftime('%d/%m/%Y')
    return False, '', None
