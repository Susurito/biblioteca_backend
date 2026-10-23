from django.db import models
from django.db.models import Q
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

def verificar_bloqueo_alumno(alumno):
    """
    Regla de Negocio RN-04:
    Si un alumno se retrasó más de 7 días en la devolución de un libro:
    - Se le aplica multa + bloqueo de 15 días.
    - Durante esos 15 días posteriores a la devolución, el alumno está bloqueado y no puede solicitar préstamos.
    - Si actualmente tiene un libro sin devolver con más de 7 días de retraso, también está bloqueado de inmediato.

    Retorna: (esta_bloqueado: bool, mensaje_error: str, fecha_desbloqueo: str | None)
    """
    if not alumno:
        return False, "", None

    ahora = timezone.now()

    # 1. Verificar si tiene préstamos activos no devueltos con más de 7 días de retraso
    prestamos_activos = Prestamos.objects.filter(
        alumno=alumno,
        devuelto=False,
        estado='aceptado'
    )
    for p in prestamos_activos:
        fv = p.fecha_vencimiento or (p.fecha_solicitud + timedelta(days=7) if p.fecha_solicitud else None)
        if fv and ahora.date() > fv.date():
            dias_retraso = (ahora.date() - fv.date()).days
            if dias_retraso > 7:
                fecha_fin = ahora + timedelta(days=15)
                fecha_str = fecha_fin.strftime('%d/%m/%Y')
                return True, (
                    f"Tu cuenta está bloqueada (RN-04). Tienes el libro '{p.libro.titulo}' "
                    f"con {dias_retraso} días de retraso. No puedes solicitar nuevos préstamos "
                    f"hasta devolverlo y cumplir la suspensión de 15 días."
                ), fecha_str

    # 2. Verificar préstamos devueltos con más de 7 días de retraso cuya suspensión de 15 días sigue vigente
    prestamos_devueltos = Prestamos.objects.filter(
        alumno=alumno,
        devuelto=True,
        fecha_devolucion__isnull=False,
        fecha_vencimiento__isnull=False
    ).order_by('-fecha_devolucion')

    for p in prestamos_devueltos:
        if p.fecha_devolucion.date() > p.fecha_vencimiento.date():
            dias_retraso = (p.fecha_devolucion.date() - p.fecha_vencimiento.date()).days
            if dias_retraso > 7:
                fecha_fin_bloqueo = p.fecha_devolucion + timedelta(days=15)
                if ahora < fecha_fin_bloqueo:
                    fecha_str = fecha_fin_bloqueo.strftime('%d/%m/%Y')
                    return True, (
                        f"Tu cuenta está suspendida hasta el {fecha_str} por haber devuelto "
                        f"el libro '{p.libro.titulo}' con {dias_retraso} días de retraso (RN-04). "
                        f"No puedes solicitar préstamos durante este periodo."
                    ), fecha_str

    return False, "", None

class PrestamosSerializer(serializers.ModelSerializer):
    alumno_nombre = serializers.CharField(source='alumno.nombre', read_only=True)
    alumno_matricula = serializers.CharField(source='alumno.matricula', read_only=True)
    alumno_nombre_completo = serializers.SerializerMethodField()
    alumno_prestamos_activos = serializers.SerializerMethodField()
    alumno_bloqueado = serializers.SerializerMethodField()
    alumno_bloqueo_motivo = serializers.SerializerMethodField()
    alumno_bloqueo_hasta = serializers.SerializerMethodField()
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
            'alumno_prestamos_activos', 'alumno_bloqueado', 'alumno_bloqueo_motivo', 'alumno_bloqueo_hasta',
            'libro', 'libro_titulo', 'libro_autor', 'libro_isbn',
            'fecha_solicitud', 'fecha_devolucion', 'fecha_vencimiento',
            'es_vencido', 'dias_vencido', 'devuelto', 'estado'
        ]
        read_only_fields = ['alumno', 'fecha_solicitud', 'fecha_devolucion', 'estado']

    def get_alumno_bloqueado(self, obj):
        if obj.alumno:
            bloqueado, _, _ = verificar_bloqueo_alumno(obj.alumno)
            return bloqueado
        return False

    def get_alumno_bloqueo_motivo(self, obj):
        if obj.alumno:
            _, motivo, _ = verificar_bloqueo_alumno(obj.alumno)
            return motivo
        return ""

    def get_alumno_bloqueo_hasta(self, obj):
        if obj.alumno:
            _, _, fecha = verificar_bloqueo_alumno(obj.alumno)
            return fecha
        return None

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

from rest_framework.pagination import PageNumberPagination

class PrestamosPagination(PageNumberPagination):
    page_size = 100
    page_size_query_param = 'page_size'
    max_page_size = 500

class PrestamosViewSet(viewsets.ModelViewSet):
    pagination_class = PrestamosPagination
    queryset = Prestamos.objects.all().order_by('devuelto', '-id')
    serializer_class = PrestamosSerializer
    permission_classes = [permissions.IsAuthenticated]

    def _es_administrador(self, user):
        if not user or not user.is_authenticated:
            return False
        return (
            user.is_superuser or
            user.groups.filter(name__iexact="Administrador").exists() or
            user.groups.filter(name__iexact="admin").exists() or
            user.groups.filter(name__iexact="administradores").exists() or
            Administradores.objects.filter(user=user).exists()
        )

    def get_queryset(self):
        user = self.request.user
        print(f"[DEBUG] get_queryset - Usuario: {user.username}, Grupos: {list(user.groups.values_list('name', flat=True))}")

        # Si es admin, ve todos los préstamos o filtrados por estado si se solicita
        if self._es_administrador(user):
            qs = Prestamos.objects.all().order_by('devuelto', '-id')
            estado = self.request.query_params.get('estado')
            if estado:
                qs = qs.filter(estado=estado)
            return qs

        # Si es alumno, solo ve sus propios préstamos
        if user.groups.filter(name__iexact="Alumno").exists():
            try:
                alumno = Alumnos.objects.get(user=user)
                return Prestamos.objects.filter(alumno=alumno).order_by('devuelto', '-id')
            except Alumnos.DoesNotExist:
                return Prestamos.objects.none()

        return Prestamos.objects.none()

    def create(self, request, *args, **kwargs):
        user = request.user
        if not self._es_administrador(user):
            try:
                alumno = Alumnos.objects.get(user=user)
                bloqueado, mensaje_bloqueo, fecha_desbloqueo = verificar_bloqueo_alumno(alumno)
                if bloqueado:
                    return Response({
                        "error": mensaje_bloqueo,
                        "bloqueado": True,
                        "fecha_desbloqueo": fecha_desbloqueo
                    }, status=status.HTTP_400_BAD_REQUEST)
            except Alumnos.DoesNotExist:
                return Response({"error": "No eres un alumno registrado."}, status=status.HTTP_400_BAD_REQUEST)
        return super().create(request, *args, **kwargs)

    # Estadísticas para el panel de préstamos del Administrador
    @action(detail=False, methods=['get'], url_path='estadisticas')
    def estadisticas(self, request):
        if not self._es_administrador(request.user):
            return Response(
                {"error": "Acceso denegado. Solo administradores pueden ver estadísticas."},
                status=status.HTTP_403_FORBIDDEN
            )
        total = Prestamos.objects.count()
        por_aprobar = Prestamos.objects.filter(devuelto=False, estado='pendiente').count()
        activos = Prestamos.objects.filter(devuelto=False, estado='aceptado').count()
        hace_7_dias = timezone.now() - timedelta(days=7)
        vencidos = Prestamos.objects.filter(
            devuelto=False,
            estado='aceptado',
            fecha_solicitud__lt=hace_7_dias
        ).count()
        historial = Prestamos.objects.filter(
            models.Q(devuelto=True) | models.Q(estado='rechazado')
        ).count()

        return Response({
            "por_aprobar": por_aprobar,
            "activos": activos,
            "vencidos": vencidos,
            "historial": historial,
            "total": total
        }, status=status.HTTP_200_OK)

    # Acción explícita para Aprobar préstamo
    @action(detail=True, methods=['post'], url_path='aprobar')
    def aprobar(self, request, pk=None):
        if not self._es_administrador(request.user):
            return Response(
                {"error": "Acceso denegado. Solo administradores pueden aprobar préstamos."},
                status=status.HTTP_403_FORBIDDEN
            )
        prestamo = self.get_object()

        if prestamo.devuelto or prestamo.estado == 'aceptado':
            return Response(
                {"error": f"El préstamo #{prestamo.id} ya se encuentra aprobado o concluido."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validar si el alumno tiene suspensión activa (RN-04)
        bloqueado, mensaje_bloqueo, _ = verificar_bloqueo_alumno(prestamo.alumno)
        if bloqueado:
            return Response(
                {"error": f"No se puede aprobar. El alumno se encuentra suspendido: {mensaje_bloqueo}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        libro = prestamo.libro
        if getattr(libro, 'baja', False):
            return Response(
                {"error": f"El libro '{libro.titulo}' está marcado como dado de baja."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validar límite de 3 préstamos activos para el alumno
        alumno_activos = Prestamos.objects.filter(alumno=prestamo.alumno, devuelto=False, estado='aceptado').count()
        if alumno_activos >= 3:
            return Response(
                {"error": f"El alumno {prestamo.alumno.nombre} ya tiene {alumno_activos} préstamos activos (máximo 3)."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validar existencias disponibles
        prestamos_activos_libro = Prestamos.objects.filter(libro=libro, devuelto=False, estado='aceptado').count()
        total_copias = getattr(libro, 'total_ejemplares', 1) or 1
        if prestamos_activos_libro >= total_copias:
            return Response(
                {"error": f"No hay copias físicas disponibles para '{libro.titulo}'. Total: {total_copias}, Activos: {prestamos_activos_libro}."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Aprobar y actualizar fecha para iniciar el periodo de 7 días
        prestamo.estado = 'aceptado'
        prestamo.fecha_solicitud = timezone.now()
        prestamo.fecha_vencimiento = prestamo.fecha_solicitud + timedelta(days=7)
        prestamo.devuelto = False
        prestamo.save()

        # Si se completó el cupo total, marcar libro como no disponible
        if (prestamos_activos_libro + 1) >= total_copias:
            libro.disponible = False
            libro.save()

        print(f"[OK] Préstamo #{prestamo.id} aprobado para {prestamo.alumno.nombre} - Libro: {libro.titulo}")
        serializer = self.get_serializer(prestamo)
        return Response({
            "message": f"Préstamo #{prestamo.id} para '{libro.titulo}' aprobado exitosamente.",
            "estado": "aceptado",
            "prestamo": serializer.data
        }, status=status.HTTP_200_OK)

    # Acción explícita para Rechazar préstamo
    @action(detail=True, methods=['post'], url_path='rechazar')
    def rechazar(self, request, pk=None):
        if not self._es_administrador(request.user):
            return Response(
                {"error": "Acceso denegado. Solo administradores pueden rechazar préstamos."},
                status=status.HTTP_403_FORBIDDEN
            )
        prestamo = self.get_object()
        prestamo.estado = 'rechazado'
        prestamo.save()

        # Recalcular disponibilidad de copias
        libro = prestamo.libro
        prestamos_activos_libro = Prestamos.objects.filter(libro=libro, devuelto=False, estado='aceptado').count()
        total_copias = getattr(libro, 'total_ejemplares', 1) or 1
        if prestamos_activos_libro < total_copias and not getattr(libro, 'baja', False):
            libro.disponible = True
            libro.save()

        print(f"[OK] Préstamo #{prestamo.id} rechazado para {prestamo.alumno.nombre}")
        serializer = self.get_serializer(prestamo)
        return Response({
            "message": f"Préstamo #{prestamo.id} para '{libro.titulo}' rechazado.",
            "estado": "rechazado",
            "prestamo": serializer.data
        }, status=status.HTTP_200_OK)

    # Acción genérica para compatibilidad: revisar_prestamo
    @action(detail=True, methods=['post'], url_path='revisar')
    def revisar_prestamo(self, request, pk=None):
        accion = request.data.get('accion')
        if accion == 'aprobar':
            return self.aprobar(request, pk)
        elif accion == 'rechazar':
            return self.rechazar(request, pk)
        else:
            return Response(
                {'error': 'Acción no válida. Use "aprobar" o "rechazar".'},
                status=status.HTTP_400_BAD_REQUEST
            )

    # Acción explícita para registrar la devolución (Solo Administradores)
    @action(detail=True, methods=['post'], url_path='devolver')
    def devolver(self, request, pk=None):
        if not self._es_administrador(request.user):
            return Response(
                {"error": "Acceso denegado. Solo los administradores pueden registrar la devolución de un libro."},
                status=status.HTTP_403_FORBIDDEN
            )
        prestamo = self.get_object()

        if prestamo.devuelto:
            return Response(
                {"error": "Este préstamo ya fue registrado como devuelto anteriormente."},
                status=status.HTTP_400_BAD_REQUEST
            )

        prestamo.devuelto = True
        prestamo.fecha_devolucion = timezone.now()
        prestamo.save()

        # Marcar el libro disponible si hay copias libres
        libro = prestamo.libro
        prestamos_activos_libro = Prestamos.objects.filter(libro=libro, devuelto=False, estado='aceptado').exclude(id=prestamo.id).count()
        total_copias = getattr(libro, 'total_ejemplares', 1) or 1
        copias_disponibles = max(0, total_copias - prestamos_activos_libro)

        if prestamos_activos_libro < total_copias and not getattr(libro, 'baja', False):
            libro.disponible = True
            libro.save()

        # Calcular métricas para el modal de Devolución registrada
        fecha_dev = prestamo.fecha_devolucion or timezone.now()
        fecha_venc = prestamo.fecha_vencimiento or (prestamo.fecha_solicitud + timedelta(days=7) if prestamo.fecha_solicitud else fecha_dev)

        dias_retraso = 0
        if fecha_dev and fecha_venc and fecha_dev.date() > fecha_venc.date():
            dias_retraso = (fecha_dev.date() - fecha_venc.date()).days

        # Aplicación estricta de Reglas de Negocio:
        # 1. Retraso 0: el modal solo dice "Devolución a tiempo, sin sanción" (sin multa, sin bloqueo).
        # 2. 1 a 7 días: solo multa ($5.00 MXN por día, RN-03). Sin bloqueo.
        # 3. Más de 7 días: multa ($5.00 MXN por día) + bloqueo de 15 días (RN-04).
        if dias_retraso == 0:
            multa_formateada = "$0"
            bloqueo_texto = "------"
            mensaje_sancion = "Devolución a tiempo, sin sanción"
        elif 1 <= dias_retraso <= 7:
            multa = dias_retraso * 5.0
            multa_formateada = f"${multa:.2f} MXN"
            bloqueo_texto = "------"
            mensaje_sancion = f"Multa de {multa_formateada} (RN-03). Sin bloqueo."
        else:  # dias_retraso > 7
            multa = dias_retraso * 5.0
            multa_formateada = f"${multa:.2f} MXN"
            fecha_fin_bloqueo = fecha_dev + timedelta(days=15)
            bloqueo_texto = f"Hasta el {fecha_fin_bloqueo.strftime('%d/%m/%Y')}"
            mensaje_sancion = f"Multa de {multa_formateada} + Bloqueo de 15 días (RN-04)"

        mensaje_stock = f"Stock actualizado: {copias_disponibles} de {total_copias} disponibles."

        detalles_devolucion = {
            "id": prestamo.id,
            "alumno_nombre": prestamo.alumno.nombre,
            "alumno_nombre_completo": f"{prestamo.alumno.nombre} {prestamo.alumno.apellido_paterno}".strip(),
            "libro_titulo": libro.titulo,
            "libro_autor": libro.autor,
            "fecha_vencimiento": fecha_venc.strftime('%d/%m/%Y') if fecha_venc else "-",
            "fecha_devolucion": fecha_dev.strftime('%d/%m/%Y') if fecha_dev else "-",
            "dias_retraso": dias_retraso,
            "multa": multa_formateada,
            "bloqueo": bloqueo_texto,
            "mensaje_sancion": mensaje_sancion,
            "stock_disponibles": copias_disponibles,
            "stock_total": total_copias,
            "stock_mensaje": mensaje_stock
        }

        print(f"[OK] Devolución registrada para préstamo #{prestamo.id} - Libro: {libro.titulo} - Retraso: {dias_retraso} días")
        serializer = self.get_serializer(prestamo)
        return Response({
            "message": f"Devolución registrada exitosamente para '{libro.titulo}'.",
            "prestamo": serializer.data,
            "detalles_devolucion": detalles_devolucion
        }, status=status.HTTP_200_OK)

    # Actualización parcial protegida para devoluciones
    def partial_update(self, request, *args, **kwargs):
        prestamo = self.get_object()

        if 'devuelto' in request.data and request.data['devuelto']:
            if not self._es_administrador(request.user):
                return Response(
                    {"error": "Acceso denegado. Solo los administradores pueden registrar la devolución de un libro."},
                    status=status.HTTP_403_FORBIDDEN
                )

            if prestamo.devuelto:
                return Response(
                    {"error": "Este préstamo ya fue registrado como devuelto anteriormente."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            prestamo.devuelto = True
            prestamo.fecha_devolucion = timezone.now()
            prestamo.save()

            libro = prestamo.libro
            prestamos_activos = Prestamos.objects.filter(libro=libro, devuelto=False, estado='aceptado').exclude(id=prestamo.id).count()
            total_copias = getattr(libro, 'total_ejemplares', 1) or 1
            if prestamos_activos < total_copias and not getattr(libro, 'baja', False):
                libro.disponible = True
                libro.save()

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

            # 1. Regla RN-04: Validar si el alumno está bloqueado / suspendido por retraso > 7 días
            bloqueado, mensaje_bloqueo, fecha_desbloqueo = verificar_bloqueo_alumno(alumno)
            if bloqueado:
                print(f"[BLOQUEO RN-04] Intento de préstamo denegado para {alumno.nombre} ({alumno.matricula}): {mensaje_bloqueo}")
                raise serializers.ValidationError({
                    "error": mensaje_bloqueo,
                    "bloqueado": True,
                    "fecha_desbloqueo": fecha_desbloqueo
                })

            # 2. Validar límite de 3 préstamos activos
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
