import uuid
from django.db import models
from .messaging_models import Outbox, Inbox, FailedMessage

class Libro(models.Model):
    isbn = models.CharField(max_length=30, blank=True, null=True, unique=True)
    titulo = models.CharField(max_length=200)
    autor = models.CharField(max_length=150)
    genero = models.CharField(max_length=100)
    detalles = models.TextField(blank=True, null=True)
    total_ejemplares = models.PositiveIntegerField(default=1)
    baja = models.BooleanField(default=False)
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

class Reserva(models.Model):
    # One physical allocation per loan, including terminal tombstones.
    prestamo_id = models.PositiveBigIntegerField(primary_key=True)
    saga_id = models.UUIDField()
    libro = models.ForeignKey(Libro, on_delete=models.PROTECT, null=True)
    estado = models.CharField(max_length=16, choices=[(s,s) for s in ('reservada','confirmada','liberada','rechazada')])
    actualizado = models.DateTimeField(auto_now=True)
