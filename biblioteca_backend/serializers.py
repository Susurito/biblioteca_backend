from rest_framework import serializers
from django.contrib.auth import get_user_model
from biblioteca_backend.models import Administradores, Alumnos, Libros, Prestamos

User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    rol = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'rol']

    def get_rol(self, obj):
        if obj.groups.filter(name="Alumno").exists():
            return 'alumnos'
        elif obj.groups.filter(name="Administrador").exists():
            return 'admin'
        return 'sin_rol'

class AdminSerializer(serializers.ModelSerializer):
    first_name = serializers.CharField(source='user.first_name', read_only=True)
    last_name = serializers.CharField(source='user.last_name', read_only=True)
    email = serializers.CharField(source='user.email', read_only=True)

    class Meta:
        model = Administradores
        fields = ['id', 'matricula', 'first_name', 'last_name', 'email', 'user_id']

class AlumnoSerializer(serializers.ModelSerializer):
    email = serializers.CharField(source='user.email', read_only=True)
    first_name = serializers.CharField(source='user.first_name', read_only=True)
    last_name = serializers.CharField(source='user.last_name', read_only=True)

    class Meta:
        model = Alumnos
        fields = [
            'id', 'matricula', 'nombre', 'apellido_paterno', 'apellido_materno',
            'first_name', 'last_name', 'email', 'user_id'
        ]

class LibrosSerializer(serializers.ModelSerializer):
    class Meta:
        model = Libros
        fields = ['id', 'titulo', 'autor', 'genero', 'detalles', 'disponible', 'creado', 'actualizado']

class PrestamosSerializer(serializers.ModelSerializer):
    # Mostrar nombre de alumno y libro para el frontend
    alumno_nombre = serializers.CharField(source='alumno.nombre', read_only=True)
    libro_titulo = serializers.CharField(source='libro.titulo', read_only=True)

    class Meta:
        model = Prestamos
        fields = ['id', 'alumno', 'alumno_nombre', 'libro', 'libro_titulo',
                  'fecha_solicitud', 'fecha_devolucion', 'devuelto', 'estado']
