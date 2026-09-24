from django.shortcuts import get_object_or_404
from django.contrib.auth.models import Group
from django.contrib.auth import get_user_model, authenticate
from rest_framework import serializers, viewsets, permissions, generics
from django.contrib.auth import get_user_model
from biblioteca_backend.models import Administradores, Alumnos, Libros, Prestamos
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone  # ⚠️ IMPORTANTE: Agregar esta importación

User = get_user_model()

# Tus serializers
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
    alumno_nombre = serializers.CharField(source='alumno.nombre', read_only=True)
    libro_titulo = serializers.CharField(source='libro.titulo', read_only=True)
    libro_autor = serializers.CharField(source='libro.autor', read_only=True)  # ⚠️ AGREGAR

    class Meta:
        model = Prestamos
        fields = ['id', 'alumno', 'alumno_nombre', 'libro', 'libro_titulo', 'libro_autor',
                  'fecha_solicitud', 'fecha_devolucion', 'devuelto', 'estado']
        read_only_fields = ['alumno', 'fecha_solicitud', 'fecha_devolucion', 'estado']

# Vistas
class LibrosViewSet(viewsets.ModelViewSet):
    queryset = Libros.objects.all()
    serializer_class = LibrosSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

class PrestamosViewSet(viewsets.ModelViewSet):
    queryset = Prestamos.objects.all()
    serializer_class = PrestamosSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        print(f"🔍 DEBUG get_queryset - Usuario: {user.username}, Grupos: {list(user.groups.values_list('name', flat=True))}")
        
        # Si es alumno, solo ve sus préstamos
        if user.groups.filter(name="Alumno").exists():
            try:
                alumno = Alumnos.objects.get(user=user)
                return Prestamos.objects.filter(alumno=alumno)
            except Alumnos.DoesNotExist:
                return Prestamos.objects.none()
        
        # Si es admin, ve todos los préstamos
        elif user.groups.filter(name="Administrador").exists():
            return Prestamos.objects.all()
        
        return Prestamos.objects.none()

    # Método para aceptar/rechazar préstamos
    @action(detail=True, methods=['post'], url_path='revisar')
    def revisar_prestamo(self, request, pk=None):
        prestamo = self.get_object()
        accion = request.data.get('accion')
        
        print(f"🔍 DEBUG revisar_prestamo - Acción: {accion}, Préstamo ID: {prestamo.id}")
        
        if accion == 'aprobar':
            prestamo.estado = 'aceptado'
            prestamo.libro.disponible = False
            prestamo.libro.save()
            prestamo.save()
            print(f"✅ Préstamo {prestamo.id} aprobado")
            return Response({
                'message': 'Préstamo aprobado exitosamente',
                'estado': 'aceptado'
            })
        
        elif accion == 'rechazar':
            prestamo.estado = 'rechazado'
            prestamo.save()
            print(f"❌ Préstamo {prestamo.id} rechazado")
            return Response({
                'message': 'Préstamo rechazado',
                'estado': 'rechazado'
            })
        
        else:
            return Response(
                {'error': 'Acción no válida. Use "aprobar" o "rechazar".'},
                status=status.HTTP_400_BAD_REQUEST
            )

    # ⚠️ MÉTODO COMPLETO PARA DEVOLUCIONES
    def partial_update(self, request, *args, **kwargs):
        prestamo = self.get_object()
        
        print(f"🔍 DEBUG partial_update - Préstamo ID: {prestamo.id}, Data: {request.data}")
        
        # Si se marca como devuelto, actualizar el libro
        if 'devuelto' in request.data and request.data['devuelto']:
            prestamo.devuelto = True
            prestamo.fecha_devolucion = timezone.now()
            
            # Marcar el libro como disponible nuevamente
            prestamo.libro.disponible = True
            prestamo.libro.save()
            
            prestamo.save()
            
            print(f"✅ Libro devuelto - Préstamo: {prestamo.id}, Libro: {prestamo.libro.titulo}")
            
            serializer = self.get_serializer(prestamo)
            return Response(serializer.data)
        
        # Para otras actualizaciones, usar el comportamiento por defecto
        return super().partial_update(request, *args, **kwargs)

class SolicitarPrestamoView(generics.CreateAPIView):
    queryset = Prestamos.objects.all()
    serializer_class = PrestamosSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        user = self.request.user
        print(f"🔍 DEBUG perform_create - Usuario: {user.username}")
        
        try:
            alumno = Alumnos.objects.get(user=user)
            print(f"✅ Alumno encontrado: {alumno.nombre}")
            
            serializer.save(alumno=alumno)
            print("✅ Préstamo guardado exitosamente")
            
        except Alumnos.DoesNotExist:
            print("❌ Error: Usuario no tiene perfil de alumno")
            raise serializers.ValidationError({
                "error": "El usuario no está registrado como alumno"
            })