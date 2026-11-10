import uuid
from django.db import models
from django.utils import timezone
from .messaging_models import Outbox, Inbox, FailedMessage

class AlumnoLock(models.Model):
    alumno_id = models.PositiveBigIntegerField(primary_key=True)

class Prestamo(models.Model):
    alumno_id = models.PositiveBigIntegerField(db_index=True)
    user_id = models.PositiveBigIntegerField(db_index=True)
    libro_id = models.PositiveBigIntegerField(db_index=True)
    alumno_snapshot = models.JSONField(default=dict)
    libro_snapshot = models.JSONField(default=dict)
    fecha_solicitud = models.DateTimeField(default=timezone.now)
    fecha_devolucion = models.DateTimeField(null=True)
    fecha_vencimiento = models.DateTimeField(null=True)
    devuelto = models.BooleanField(default=False)
    estado = models.CharField(max_length=10, default='pendiente', choices=[(s,s) for s in ('pendiente','aceptado','rechazado')])
    multa_pagada = models.BooleanField(default=False)
    fecha_pago_multa = models.DateTimeField(null=True)

class Saga(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    prestamo = models.ForeignKey(Prestamo, on_delete=models.PROTECT, related_name='operaciones')
    tipo = models.CharField(max_length=12)
    estado = models.CharField(max_length=16)
    resultado = models.JSONField(default=dict)
    error = models.TextField(blank=True)
    creado = models.DateTimeField(default=timezone.now)
    actualizado = models.DateTimeField(default=timezone.now)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['prestamo','tipo'], name='one_operation_per_loan_kind')]
