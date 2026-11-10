"""
Modelos propios de svc-usuarios.

Copia exacta de los modelos Administradores y Alumnos del monolito.
La tabla Prestamos NO se incluye aquí — pertenece a svc-prestamos (Fase 4).

Nota: Las referencias a Libros y Prestamos que existían como FK en el
monolito se convierten en PositiveIntegerField al momento de migrar
svc-prestamos (Fase 4). Aquí solo gestionamos usuarios.
"""

from django.db import models
from django.contrib.auth.models import User


class Administradores(models.Model):
    id = models.BigAutoField(primary_key=True)
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    matricula = models.CharField(max_length=9, unique=True)
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'usuarios_service_administradores'
        verbose_name = 'Administrador'
        verbose_name_plural = 'Administradores'

    def __str__(self):
        return f"Administrador: {self.user.first_name} {self.user.last_name}"


class Alumnos(models.Model):
    id = models.BigAutoField(primary_key=True)
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    matricula = models.CharField(max_length=10, unique=True)
    nombre = models.CharField(max_length=50)
    apellido_paterno = models.CharField(max_length=50)
    apellido_materno = models.CharField(max_length=50)
    rol = models.CharField(max_length=20, default='Estudiante', verbose_name="Rol")
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'usuarios_service_alumnos'
        verbose_name = 'Alumno'
        verbose_name_plural = 'Alumnos'

    def __str__(self):
        return f"{self.nombre} {self.apellido_paterno} {self.apellido_materno}"
