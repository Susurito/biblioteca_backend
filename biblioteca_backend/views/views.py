from django.conf import settings
from django.db import transaction
from django.db import models
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model
from rest_framework import viewsets, permissions, generics
from rest_framework import serializers
from biblioteca_backend.models import Administradores, Alumnos, Libros, Prestamos
from biblioteca_backend.serializers import (
    LibrosSerializer,
    PrestamosSerializer,
)
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from datetime import timedelta
from django.utils import timezone

User = get_user_model()


def verificar_bloqueo_alumno(alumno):
    """
    Regla de Negocio RN-04:
    Si un alumno se retrasó más de 7 días en la devolución de un libro:
    - Se le aplica multa + bloqueo de 15 días.
    - Durante esos 15 días posteriores a la devolución, el alumno está bloqueado
      y no puede solicitar préstamos.
    - Si actualmente tiene un libro sin devolver con más de 7 días de retraso,
      también está bloqueado de inmediato.

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

    # 2. Verificar préstamos devueltos con más de 7 días de retraso cuya suspensión sigue vigente
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
        if not self._es_administrador(request.user):
            return Response(
                {"error": "Acceso denegado. Solo los administradores pueden registrar libros."},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"error": "Datos inválidos", "detalles": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )

        self.perform_create(serializer)
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

        for libro in libros:
            if getattr(libro, 'baja', False):
                dados_de_baja += 1
            else:
                prestados = libro.prestamos.filter(devuelto=False, estado='aceptado').count()
                total = getattr(libro, 'total_ejemplares', 1) or 1
                disponibles = max(0, total - prestados)
                if disponibles <= 0 or not libro.disponible:
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


def locked_legacy_loan(pid):
    preview = Prestamos.objects.get(pk=pid)
    Alumnos.objects.select_for_update().get(pk=preview.alumno_id)
    Libros.objects.select_for_update().get(pk=preview.libro_id)
    return Prestamos.objects.select_for_update().get(pk=pid)


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
        return SolicitarPrestamoView.as_view()(request._request)

    def update(self, request, *args, **kwargs):
        raise serializers.ValidationError('Usa acciones explícitas.')

    def destroy(self, request, *args, **kwargs):
        raise serializers.ValidationError('El historial de préstamos se conserva.')

    @action(detail=False, methods=['get'], url_path='estadisticas')
    def estadisticas(self, request):
        """Estadísticas para el panel de préstamos del Administrador."""
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

    @action(detail=True, methods=['post'], url_path='aprobar')
    @transaction.atomic
    def aprobar(self, request, pk=None):
        if settings.CATALOG_REMOTE_ENABLED:
            from biblioteca_backend.migration_bridge import legacy_action
            if not self._es_administrador(request.user):
                return Response({'error':'Solo administradores.'}, status=403)
            return Response(legacy_action(self.get_object().pk, 'aprobar'))
        """Acción explícita para aprobar un préstamo (Solo Administradores)."""
        if not self._es_administrador(request.user):
            return Response(
                {"error": "Acceso denegado. Solo administradores pueden aprobar préstamos."},
                status=status.HTTP_403_FORBIDDEN
            )
        prestamo = locked_legacy_loan(self.get_object().pk)

        if prestamo.devuelto or prestamo.estado != 'pendiente':
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

        serializer = self.get_serializer(prestamo)
        return Response({
            "message": f"Préstamo #{prestamo.id} para '{libro.titulo}' aprobado exitosamente.",
            "estado": "aceptado",
            "prestamo": serializer.data
        }, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='rechazar')
    @transaction.atomic
    def rechazar(self, request, pk=None):
        if settings.CATALOG_REMOTE_ENABLED:
            from biblioteca_backend.migration_bridge import legacy_action
            if not self._es_administrador(request.user):
                return Response({'error':'Solo administradores.'}, status=403)
            return Response(legacy_action(self.get_object().pk, 'rechazar'))
        """Acción explícita para rechazar un préstamo (Solo Administradores)."""
        if not self._es_administrador(request.user):
            return Response(
                {"error": "Acceso denegado. Solo administradores pueden rechazar préstamos."},
                status=status.HTTP_403_FORBIDDEN
            )
        prestamo = locked_legacy_loan(self.get_object().pk)
        if prestamo.estado != 'pendiente' or prestamo.devuelto:
            raise serializers.ValidationError('Solo se rechazan solicitudes pendientes.')
        prestamo.estado = 'rechazado'
        prestamo.save()

        # Recalcular disponibilidad de copias
        libro = prestamo.libro
        prestamos_activos_libro = Prestamos.objects.filter(libro=libro, devuelto=False, estado='aceptado').count()
        total_copias = getattr(libro, 'total_ejemplares', 1) or 1
        if prestamos_activos_libro < total_copias and not getattr(libro, 'baja', False):
            libro.disponible = True
            libro.save()

        serializer = self.get_serializer(prestamo)
        return Response({
            "message": f"Préstamo #{prestamo.id} para '{libro.titulo}' rechazado.",
            "estado": "rechazado",
            "prestamo": serializer.data
        }, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='revisar')
    def revisar_prestamo(self, request, pk=None):
        """Acción genérica para compatibilidad: delega a aprobar o rechazar."""
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

    @action(detail=True, methods=['post'], url_path='devolver')
    @transaction.atomic
    def devolver(self, request, pk=None):
        if settings.CATALOG_REMOTE_ENABLED:
            from biblioteca_backend.migration_bridge import legacy_action
            if not self._es_administrador(request.user):
                return Response({'error':'Solo administradores.'}, status=403)
            return Response(legacy_action(self.get_object().pk, 'devolver'))
        """Acción explícita para registrar la devolución (Solo Administradores)."""
        if not self._es_administrador(request.user):
            return Response(
                {"error": "Acceso denegado. Solo los administradores pueden registrar la devolución de un libro."},
                status=status.HTTP_403_FORBIDDEN
            )
        prestamo = locked_legacy_loan(self.get_object().pk)

        if prestamo.estado != 'aceptado':
            raise serializers.ValidationError('Solo se devuelven préstamos activos.')
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
        prestamos_activos_libro = Prestamos.objects.filter(
            libro=libro, devuelto=False, estado='aceptado'
        ).exclude(id=prestamo.id).count()
        total_copias = getattr(libro, 'total_ejemplares', 1) or 1
        copias_disponibles = max(0, total_copias - prestamos_activos_libro)

        if prestamos_activos_libro < total_copias and not getattr(libro, 'baja', False):
            libro.disponible = True
            libro.save()

        # Calcular métricas de devolución y sanciones
        fecha_dev = prestamo.fecha_devolucion or timezone.now()
        fecha_venc = prestamo.fecha_vencimiento or (
            prestamo.fecha_solicitud + timedelta(days=7) if prestamo.fecha_solicitud else fecha_dev
        )

        dias_retraso = 0
        if fecha_dev and fecha_venc and fecha_dev.date() > fecha_venc.date():
            dias_retraso = (fecha_dev.date() - fecha_venc.date()).days

        # Reglas de negocio:
        # RN-03: Retraso 1-7 días → multa ($5.00 MXN/día), sin bloqueo.
        # RN-04: Retraso >7 días → multa + bloqueo de 15 días.
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

        serializer = self.get_serializer(prestamo)
        return Response({
            "message": f"Devolución registrada exitosamente para '{libro.titulo}'.",
            "prestamo": serializer.data,
            "detalles_devolucion": detalles_devolucion
        }, status=status.HTTP_200_OK)

    def partial_update(self, request, *args, **kwargs):
        if request.data == {'devuelto': True}:
            return self.devolver(request, kwargs.get('pk'))
        raise serializers.ValidationError('Usa las acciones explícitas del préstamo.')


class SolicitarPrestamoView(generics.CreateAPIView):
    @transaction.atomic
    def create(self, request, *args, **kwargs):
        if settings.CATALOG_REMOTE_ENABLED:
            from biblioteca_backend.migration_bridge import project_book
            bid = serializers.IntegerField(min_value=1).run_validation(request.data.get('libro'))
            project_book(bid)
        return super().create(request, *args, **kwargs)

    queryset = Prestamos.objects.all()
    serializer_class = PrestamosSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        user = self.request.user

        try:
            alumno = Alumnos.objects.select_for_update().get(user=user)

            # 1. Regla RN-04: Validar si el alumno está bloqueado por retraso > 7 días
            bloqueado, mensaje_bloqueo, fecha_desbloqueo = verificar_bloqueo_alumno(alumno)
            if bloqueado:
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

            # 3. Validar si ya tiene una solicitud pendiente o activa para el mismo libro
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

        except Alumnos.DoesNotExist:
            raise serializers.ValidationError({
                "error": "El usuario no está registrado como alumno"
            })
