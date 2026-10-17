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

from datetime import timedelta

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
        if obj.fecha_solicitud:
            return obj.fecha_solicitud + timedelta(days=7)
        return None

    def get_es_vencido(self, obj):
        if obj.devuelto or obj.estado != 'aceptado':
            return False
        if obj.fecha_solicitud:
            return timezone.now() > (obj.fecha_solicitud + timedelta(days=7))
        return False

    def get_dias_vencido(self, obj):
        if obj.devuelto or obj.estado != 'aceptado':
            return 0
        if obj.fecha_solicitud:
            vence = obj.fecha_solicitud + timedelta(days=7)
            now = timezone.now()
            if now > vence:
                return (now - vence).days or 1
        return 0

# Permiso personalizado para libros: lectura pública o autenticada, escritura solo admin
class IsAdminOrReadOnly(permissions.BasePermission):
    """
    Permite lectura (GET, HEAD, OPTIONS) a cualquier usuario,
    pero operaciones de escritura (POST, PUT, PATCH, DELETE) solo a Administradores.
    """
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        user = request.user
        if not (user and user.is_authenticated):
            return False
        return bool(
            user.is_superuser or
            user.groups.filter(name__iexact="Administrador").exists() or
            user.groups.filter(name__iexact="admin").exists() or
            Administradores.objects.filter(user=user).exists()
        )

# Vistas
class LibrosViewSet(viewsets.ModelViewSet):
    queryset = Libros.objects.all().order_by('-id')
    serializer_class = LibrosSerializer
    permission_classes = [IsAdminOrReadOnly]

    def _es_administrador(self, user):
        """Verifica si el usuario autenticado cuenta con rol de Administrador."""
        if not user or not user.is_authenticated:
            return False
        return (
            user.is_superuser or
            user.groups.filter(name__iexact="Administrador").exists() or
            user.groups.filter(name__iexact="admin").exists() or
            Administradores.objects.filter(user=user).exists()
        )

    def create(self, request, *args, **kwargs):
        """
        Registrar un nuevo libro (POST /libros/).
        Función exclusiva para usuarios con rol de Administrador.
        """
        user = request.user
        username = user.username if user.is_authenticated else "Anónimo"
        print(f"DEBUG registrar_libro - Usuario: {username}, Autenticado: {user.is_authenticated}")

        if not self._es_administrador(user):
            print(f"Acceso denegado: El usuario '{username}' no tiene rol de Administrador")
            return Response(
                {"error": "Acceso denegado. Solo los administradores pueden registrar libros."},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            print(f"Error de validación al registrar libro: {serializer.errors}")
            return Response(
                {"error": "Datos inválidos", "detalles": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )

        self.perform_create(serializer)
        print(f"Libro registrado exitosamente: '{serializer.data.get('titulo')}' por {username}")
        return Response(
            {
                "message": "Libro registrado exitosamente",
                "libro": serializer.data
            },
            status=status.HTTP_201_CREATED
        )

    @action(detail=False, methods=['post'], url_path='registrar')
    def registrar_libro(self, request):
        """
        Endpoint explícito: POST /libros/registrar/
        Acción para registrar libros restringida al rol de Administrador.
        """
        return self.create(request)

    @action(detail=True, methods=['post'], url_path='dar-de-baja')
    def dar_de_baja(self, request, pk=None):
        libro = self.get_object()
        if not self._es_administrador(request.user):
            return Response(
                {"error": "Acceso denegado. Solo administradores pueden dar de baja libros."},
                status=status.HTTP_403_FORBIDDEN
            )
        libro.baja = True
        libro.save()
        serializer = self.get_serializer(libro)
        return Response({
            "message": f"El libro '{libro.titulo}' ha sido dado de baja exitosamente.",
            "libro": serializer.data
        })

    @action(detail=True, methods=['post'], url_path='dar-de-alta')
    def dar_de_alta(self, request, pk=None):
        libro = self.get_object()
        if not self._es_administrador(request.user):
            return Response(
                {"error": "Acceso denegado. Solo administradores pueden dar de alta libros."},
                status=status.HTTP_403_FORBIDDEN
            )
        libro.baja = False
        libro.save()
        serializer = self.get_serializer(libro)
        return Response({
            "message": f"El libro '{libro.titulo}' ha sido reactivado exitosamente.",
            "libro": serializer.data
        })

    @action(detail=False, methods=['get'], url_path='estadisticas')
    def estadisticas(self, request):
        libros = Libros.objects.all()
        activos = 0
        sin_stock = 0
        dados_de_baja = 0

        for l in libros:
            if getattr(l, 'baja', False):
                dados_de_baja += 1
            else:
                prestados = l.prestamos.filter(devuelto=False, estado='aceptado').count()
                total = getattr(l, 'total_ejemplares', 1) or 1
                disponibles = max(0, total - prestados)
                if disponibles <= 0 or not l.disponible:
                    sin_stock += 1
                else:
                    activos += 1

        return Response({
            "activos": activos,
            "sin_stock": sin_stock,
            "dados_de_baja": dados_de_baja,
            "total": libros.count()
        })

    @action(detail=False, methods=['get'], url_path='recomendados')
    def recomendados(self, request):
        """
        Endpoint: GET /libros/recomendados/
        Retorna libros recomendados desde la base de datos.
        Para alumnos autenticados:
        - Excluye libros que el alumno ya tiene prestados actualmente.
        - Prioriza libros disponibles de los géneros que más ha solicitado o leído.
        - Si no hay historial suficiente, completa con los libros más recientes o disponibles.
        """
        user = request.user
        libros_qs = Libros.objects.all()

        alumno = None
        if user and user.is_authenticated:
            alumno = Alumnos.objects.filter(user=user).first()

        ids_excluir = []
        generos_favoritos = []

        if alumno:
            prestamos_alumno = Prestamos.objects.filter(alumno=alumno)
            ids_excluir = list(prestamos_alumno.filter(devuelto=False).values_list('libro_id', flat=True))
            generos_favoritos = list(
                prestamos_alumno.values_list('libro__genero', flat=True).distinct()
            )

        candidatos = libros_qs.exclude(id__in=ids_excluir)
        recomendados_list = []

        # 1. Libros disponibles de géneros favoritos
        if generos_favoritos:
            favoritos = list(candidatos.filter(genero__in=generos_favoritos, disponible=True).order_by('-id')[:6])
            recomendados_list.extend(favoritos)

        # 2. Completar con otros libros disponibles
        if len(recomendados_list) < 6:
            ids_ya_agregados = [b.id for b in recomendados_list] + ids_excluir
            otros_disponibles = list(
                candidatos.exclude(id__in=ids_ya_agregados).filter(disponible=True).order_by('-id')[:(6 - len(recomendados_list))]
            )
            recomendados_list.extend(otros_disponibles)

        # 3. Si aún hay pocos, completar con libros generales
        if len(recomendados_list) < 3:
            ids_ya_agregados = [b.id for b in recomendados_list]
            otros_general = list(
                libros_qs.exclude(id__in=ids_ya_agregados).order_by('-id')[:(6 - len(recomendados_list))]
            )
            recomendados_list.extend(otros_general)

        serializer = self.get_serializer(recomendados_list, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def update(self, request, *args, **kwargs):
        """Modificar libro (PUT /libros/{id}/) - Solo Administradores."""
        if not self._es_administrador(request.user):
            return Response(
                {"error": "Acceso denegado. Solo los administradores pueden modificar libros."},
                status=status.HTTP_403_FORBIDDEN
            )
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        """Actualización parcial de libro (PATCH /libros/{id}/) - Solo Administradores."""
        if not self._es_administrador(request.user):
            return Response(
                {"error": "Acceso denegado. Solo los administradores pueden modificar libros."},
                status=status.HTTP_403_FORBIDDEN
            )
        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        """Eliminar libro (DELETE /libros/{id}/) - Solo Administradores."""
        if not self._es_administrador(request.user):
            return Response(
                {"error": "Acceso denegado. Solo los administradores pueden eliminar libros."},
                status=status.HTTP_403_FORBIDDEN
            )
        return super().destroy(request, *args, **kwargs)

class PrestamosViewSet(viewsets.ModelViewSet):
    queryset = Prestamos.objects.all().order_by('-fecha_solicitud')
    serializer_class = PrestamosSerializer
    permission_classes = [permissions.IsAuthenticated]

    def _es_administrador(self, user):
        if not user or not user.is_authenticated:
            return False
        return (
            user.is_superuser or
            user.groups.filter(name__iexact="Administrador").exists() or
            user.groups.filter(name__iexact="admin").exists() or
            Administradores.objects.filter(user=user).exists()
        )

    def get_queryset(self):
        user = self.request.user
        print(f"[DEBUG] get_queryset - Usuario: {user.username}, Grupos: {list(user.groups.values_list('name', flat=True))}")

        # Si es admin, ve todos los préstamos ordenados por fecha
        if self._es_administrador(user):
            return Prestamos.objects.all().order_by('-fecha_solicitud')

        # Si es alumno, solo ve sus propios préstamos
        if user.groups.filter(name__iexact="Alumno").exists():
            try:
                alumno = Alumnos.objects.get(user=user)
                return Prestamos.objects.filter(alumno=alumno).order_by('-fecha_solicitud')
            except Alumnos.DoesNotExist:
                return Prestamos.objects.none()

        return Prestamos.objects.none()


    # Acción explícita para registrar la devolución (Solo Administradores)
    @action(detail=True, methods=['post'], url_path='devolver')
    def devolver(self, request, pk=None):
        if not self._es_administrador(request.user):
            return Response(
                {"error": "Acceso denegado. Solo los administradores pueden registrar la devolución de un libro."},
                status=status.HTTP_403_FORBIDDEN
            )
        prestamo = self.get_object()
        prestamo.devuelto = True
        prestamo.fecha_devolucion = timezone.now()

        # Marcar el libro disponible nuevamente
        prestamo.libro.disponible = True
        prestamo.libro.save()
        prestamo.save()

        print(f"[OK] Devolución registrada para préstamo #{prestamo.id} - Libro: {prestamo.libro.titulo}")
        serializer = self.get_serializer(prestamo)
        return Response({
            "message": f"Devolución registrada exitosamente para '{prestamo.libro.titulo}'.",
            "prestamo": serializer.data
        }, status=status.HTTP_200_OK)

    # Método para aceptar/rechazar préstamos pendientes
    @action(detail=True, methods=['post'], url_path='revisar')
    def revisar_prestamo(self, request, pk=None):
        if not self._es_administrador(request.user):
            return Response(
                {"error": "Acceso denegado. Solo administradores pueden revisar préstamos."},
                status=status.HTTP_403_FORBIDDEN
            )
        prestamo = self.get_object()
        accion = request.data.get('accion')

        print(f"[DEBUG] revisar_prestamo - Acción: {accion}, Préstamo ID: {prestamo.id}")

        if accion == 'aprobar':
            prestamo.estado = 'aceptado'
            prestamo.libro.disponible = False
            prestamo.libro.save()
            prestamo.save()
            print(f"[OK] Préstamo {prestamo.id} aprobado")
            return Response({
                'message': 'Préstamo aprobado exitosamente',
                'estado': 'aceptado'
            })

        elif accion == 'rechazar':
            prestamo.estado = 'rechazado'
            prestamo.save()
            print(f"[ERROR] Préstamo {prestamo.id} rechazado")
            return Response({
                'message': 'Préstamo rechazado',
                'estado': 'rechazado'
            })

        else:
            return Response(
                {'error': 'Acción no válida. Use "aprobar" o "rechazar".'},
                status=status.HTTP_400_BAD_REQUEST
            )

    # Actualización parcial protegida para devoluciones
    def partial_update(self, request, *args, **kwargs):
        prestamo = self.get_object()

        # Si se intenta marcar como devuelto, verificar rol de administrador
        if 'devuelto' in request.data and request.data['devuelto']:
            if not self._es_administrador(request.user):
                return Response(
                    {"error": "Acceso denegado. Solo los administradores pueden registrar la devolución de un libro."},
                    status=status.HTTP_403_FORBIDDEN
                )
            prestamo.devuelto = True
            prestamo.fecha_devolucion = timezone.now()
            prestamo.libro.disponible = True
            prestamo.libro.save()
            prestamo.save()

            print(f"[OK] Libro devuelto - Préstamo: {prestamo.id}, Libro: {prestamo.libro.titulo}")
            serializer = self.get_serializer(prestamo)
            return Response(serializer.data)

        return super().partial_update(request, *args, **kwargs)

class SolicitarPrestamoView(generics.CreateAPIView):
    queryset = Prestamos.objects.all()
    serializer_class = PrestamosSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        user = self.request.user
        print(f"DEBUG perform_create - Usuario: {user.username}")

        try:
            alumno = Alumnos.objects.get(user=user)
            print(f"Alumno encontrado: {alumno.nombre}")

            # Validar límite de 3 préstamos activos
            activos = Prestamos.objects.filter(alumno=alumno, devuelto=False, estado='aceptado').count()
            if activos >= 3:
                raise serializers.ValidationError({
                    "error": f"Ya tienes {activos} de 3 préstamos activos. No puedes solicitar más libros hasta devolver alguno."
                })

            libro = serializer.validated_data.get('libro')
            if libro and not libro.disponible:
                raise serializers.ValidationError({
                    "error": f"El libro '{libro.titulo}' no está disponible actualmente para préstamo."
                })

            # Validar si ya tiene una solicitud pendiente o activa para el mismo libro
            prestamo_existente = Prestamos.objects.filter(
                alumno=alumno,
                libro=libro,
                devuelto=False
            ).exclude(estado='rechazado').first()
            if prestamo_existente:
                raise serializers.ValidationError({
                    "error": f"Ya tienes una solicitud en estado '{prestamo_existente.estado}' para este libro."
                })

            serializer.save(alumno=alumno, estado='pendiente', devuelto=False)
            print("[OK] Préstamo guardado exitosamente en estado pendiente")

        except Alumnos.DoesNotExist:
            print("Error: Usuario no tiene perfil de alumno")
            raise serializers.ValidationError({
                "error": "El usuario no está registrado como alumno"
            })
