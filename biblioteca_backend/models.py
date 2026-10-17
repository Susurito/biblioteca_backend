from django.db import models
from django.contrib.auth.models import User

# ---------------------------
# Modelo para Administradores
# ---------------------------
class Administradores(models.Model):
    id = models.BigAutoField(primary_key=True)
    user = models.OneToOneField(User, on_delete=models.CASCADE)  # Relación 1 a 1 con User
    matricula = models.CharField(max_length=9, unique=True)      # Solo 9 dígitos
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Administrador: {self.user.first_name} {self.user.last_name}"


# ---------------------------
# Modelo para Alumnos
# ---------------------------
class Alumnos(models.Model):
    id = models.BigAutoField(primary_key=True)
    user = models.OneToOneField(User, on_delete=models.CASCADE)  # Relación 1 a 1 con User
    matricula = models.CharField(max_length=10, unique=True)
    nombre = models.CharField(max_length=50)       # Copia del first_name
    apellido_paterno = models.CharField(max_length=50)
    apellido_materno = models.CharField(max_length=50)
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.nombre} {self.apellido_paterno} {self.apellido_materno}"

class Libros(models.Model):
    id = models.BigAutoField(primary_key=True)   # Se auto-incrementa automáticamente
    isbn = models.CharField(max_length=30, blank=True, null=True, unique=True, verbose_name="ISBN")
    titulo = models.CharField(max_length=200)
    autor = models.CharField(max_length=150)
    genero = models.CharField(max_length=100)
    detalles = models.TextField(blank=True, null=True)
    disponible = models.BooleanField(default=True)  # Disponible o No disponible

    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.titulo} - {self.autor}"
    

class Prestamos(models.Model):
    id = models.BigAutoField(primary_key=True)
    alumno = models.ForeignKey(Alumnos, on_delete=models.CASCADE, related_name='prestamos')
    libro = models.ForeignKey(Libros, on_delete=models.CASCADE, related_name='prestamos')
    fecha_solicitud = models.DateTimeField(auto_now_add=True)
    fecha_devolucion = models.DateTimeField(blank=True, null=True)
    devuelto = models.BooleanField(default=False)

    ESTADOS = [
        ('pendiente', 'Pendiente'),
        ('aceptado', 'Aceptado'),
        ('rechazado', 'Rechazado'),
    ]
    estado = models.CharField(max_length=10, choices=ESTADOS, default='pendiente')

    def __str__(self):
        return f"Préstamo de {self.libro.titulo} a {self.alumno.nombre} ({self.estado})"
