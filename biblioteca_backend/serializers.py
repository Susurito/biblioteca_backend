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

from datetime import timedelta
from django.utils import timezone

class AlumnoSerializer(serializers.ModelSerializer):
    email = serializers.CharField(source='user.email', read_only=True)
    first_name = serializers.CharField(source='user.first_name', read_only=True)
    last_name = serializers.CharField(source='user.last_name', read_only=True)
    nombre_completo = serializers.SerializerMethodField()
    prestamos_activos = serializers.SerializerMethodField()

    class Meta:
        model = Alumnos
        fields = [
            'id', 'matricula', 'nombre', 'apellido_paterno', 'apellido_materno',
            'nombre_completo', 'first_name', 'last_name', 'email', 'user_id', 'prestamos_activos'
        ]

    def get_nombre_completo(self, obj):
        partes = [obj.nombre, obj.apellido_paterno, obj.apellido_materno]
        return " ".join([p for p in partes if p]).strip()

    def get_prestamos_activos(self, obj):
        return obj.prestamos.filter(devuelto=False, estado='aceptado').count()

class LibrosSerializer(serializers.ModelSerializer):
    total_ejemplares = serializers.IntegerField(required=False, default=1)
    baja = serializers.BooleanField(required=False, default=False)
    disponibles = serializers.SerializerMethodField()
    prestados = serializers.SerializerMethodField()
    estado_ejemplar = serializers.SerializerMethodField()

    class Meta:
        model = Libros
        fields = [
            'id', 'isbn', 'titulo', 'autor', 'genero', 'detalles',
            'disponible', 'total_ejemplares', 'baja',
            'disponibles', 'prestados', 'estado_ejemplar',
            'creado', 'actualizado'
        ]

    def validate_isbn(self, value):
        if value is not None:
            value = str(value).strip()
            if value == "":
                return None
        return value

    def get_prestados(self, obj):
        try:
            return obj.prestamos.filter(devuelto=False, estado='aceptado').count()
        except Exception:
            return 0

    def get_disponibles(self, obj):
        if getattr(obj, 'baja', False):
            return 0
        prestados = self.get_prestados(obj)
        total = getattr(obj, 'total_ejemplares', 1) or 1
        return max(0, total - prestados)

    def get_estado_ejemplar(self, obj):
        if getattr(obj, 'baja', False):
            return 'dado_de_baja'
        disponibles = self.get_disponibles(obj)
        if disponibles <= 0 or not getattr(obj, 'disponible', True):
            return 'sin_stock'
        return 'disponible'

class PrestamosSerializer(serializers.ModelSerializer):
    alumno_nombre = serializers.CharField(source='alumno.nombre', read_only=True)
    alumno_matricula = serializers.CharField(source='alumno.matricula', read_only=True)
    alumno_nombre_completo = serializers.SerializerMethodField()
    alumno_prestamos_activos = serializers.SerializerMethodField()
    libro_titulo = serializers.CharField(source='libro.titulo', read_only=True)
    libro_autor = serializers.CharField(source='libro.autor', read_only=True)
    libro_isbn = serializers.CharField(source='libro.isbn', read_only=True)
    fecha_vencimiento = serializers.SerializerMethodField()
    es_vencido = serializers.SerializerMethodField()
    dias_vencido = serializers.SerializerMethodField()

    class Meta:
        model = Prestamos
        fields = [
            'id', 'alumno', 'alumno_nombre', 'alumno_matricula', 'alumno_nombre_completo',
            'alumno_prestamos_activos', 'libro', 'libro_titulo', 'libro_autor', 'libro_isbn',
            'fecha_solicitud', 'fecha_devolucion', 'fecha_vencimiento',
            'es_vencido', 'dias_vencido', 'devuelto', 'estado'
        ]
        read_only_fields = ['alumno', 'fecha_solicitud', 'fecha_devolucion', 'estado']

    def get_alumno_nombre_completo(self, obj):
        if obj.alumno:
            partes = [obj.alumno.nombre, obj.alumno.apellido_paterno, obj.alumno.apellido_materno]
            return " ".join([p for p in partes if p]).strip()
        return ""

    def get_alumno_prestamos_activos(self, obj):
        if obj.alumno:
            return obj.alumno.prestamos.filter(devuelto=False, estado='aceptado').count()
        return 0

    def get_fecha_vencimiento(self, obj):
        if obj.fecha_vencimiento:
            return obj.fecha_vencimiento
        if obj.fecha_solicitud and obj.estado != 'pendiente':
            return obj.fecha_solicitud + timedelta(days=7)
        return None

    def get_es_vencido(self, obj):
        if obj.devuelto or obj.estado != 'aceptado':
            return False
        fv = obj.fecha_vencimiento or (obj.fecha_solicitud + timedelta(days=7) if obj.fecha_solicitud else None)
        if fv:
            return timezone.now() > fv
        return False

    def get_dias_vencido(self, obj):
        if obj.devuelto or obj.estado != 'aceptado':
            return 0
        fv = obj.fecha_vencimiento or (obj.fecha_solicitud + timedelta(days=7) if obj.fecha_solicitud else None)
        if fv:
            now = timezone.now()
            if now > fv:
                return (now.date() - fv.date()).days or 1
        return 0
