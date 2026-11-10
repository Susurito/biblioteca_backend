from django.conf import settings
from django.db import transaction
from django.db.models import Count, Q
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from biblioteca_common.auth import AdminOrReadOnly, InternalOnly
from biblioteca_common.http import call
from .models import Libro, Reserva
from .domain import occupied

class LibroSerializer(serializers.ModelSerializer):
    prestados = serializers.SerializerMethodField()
    disponibles = serializers.SerializerMethodField()
    disponible = serializers.SerializerMethodField()
    estado_ejemplar = serializers.SerializerMethodField()
    class Meta:
        model = Libro
        fields = ['id','isbn','titulo','autor','genero','detalles','total_ejemplares','baja',
                  'creado','actualizado','prestados','disponibles','disponible','estado_ejemplar']
        read_only_fields = ['id','creado','actualizado']
    def get_prestados(self, obj):
        return getattr(obj, 'ocupados', 0)
    def get_disponibles(self, obj):
        return 0 if obj.baja else max(0, obj.total_ejemplares-self.get_prestados(obj))
    def get_disponible(self, obj):
        return self.get_disponibles(obj) > 0
    def get_estado_ejemplar(self, obj):
        return 'dado_de_baja' if obj.baja else 'disponible' if self.get_disponible(obj) else 'sin_stock'
    def validate_isbn(self, value):
        return value.strip() or None if value else None

class LibrosViewSet(viewsets.ModelViewSet):
    serializer_class = LibroSerializer
    permission_classes = [AdminOrReadOnly]
    def get_queryset(self):
        qs = Libro.objects.annotate(ocupados=Count('reserva', filter=Q(reserva__estado__in=['reservada','confirmada']))).order_by('-id')
        query = self.request.query_params.get('search') or self.request.query_params.get('q')
        if query:
            qs = qs.filter(Q(titulo__icontains=query)|Q(autor__icontains=query)|Q(isbn__icontains=query))
        return qs
    @action(detail=False, methods=['post'], url_path='registrar')
    def registrar(self, request):
        return self.create(request)
    @transaction.atomic
    def perform_update(self, serializer):
        book = Libro.objects.select_for_update().get(pk=serializer.instance.pk)
        count = occupied(book)
        if serializer.validated_data.get('total_ejemplares', book.total_ejemplares) < count:
            raise ValidationError({'total_ejemplares': 'Hay ejemplares reservados o prestados.'})
        if serializer.validated_data.get('baja', book.baja) and count:
            raise ValidationError({'baja': 'Hay ejemplares reservados o prestados.'})
        serializer.instance = book
        book.ocupados = count
        serializer.save()
    def destroy(self, request, *args, **kwargs):
        # Retain bibliographic references for historical loans.
        raise ValidationError({'detail': 'Usa dar-de-baja para conservar el historial.'})
    @action(detail=True, methods=['post'], url_path='dar-de-baja')
    @transaction.atomic
    def dar_de_baja(self, request, pk=None):
        book = Libro.objects.select_for_update().get(pk=self.get_object().pk)
        if occupied(book):
            raise ValidationError('Hay ejemplares reservados o prestados.')
        book.baja = True
        book.save()
        return Response(self.get_serializer(self.get_queryset().get(pk=book.pk)).data)
    @action(detail=True, methods=['post'], url_path='dar-de-alta')
    @transaction.atomic
    def dar_de_alta(self, request, pk=None):
        book = Libro.objects.select_for_update().get(pk=self.get_object().pk)
        book.baja = False
        book.save()
        return Response(self.get_serializer(self.get_queryset().get(pk=book.pk)).data)
    @action(detail=False, methods=['get'])
    def estadisticas(self, request):
        from biblioteca_common.auth import IsAdmin
        if not IsAdmin().has_permission(request, self):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied()
        books = list(self.get_queryset())
        return Response({'activos': sum(not b.baja and b.total_ejemplares>b.ocupados for b in books),
                         'sin_stock': sum(not b.baja and b.total_ejemplares<=b.ocupados for b in books),
                         'dados_de_baja': sum(b.baja for b in books), 'total': len(books)})
    @action(detail=False, methods=['get'])
    def recomendados(self, request):
        qs = self.get_queryset().filter(baja=False)
        if request.user.is_authenticated and getattr(request.user, 'alumno_id', None):
            history = call(settings.LOANS_URL, '/internal/historial/', {'alumno_id': request.user.alumno_id})
            ids = {p['libro'] for p in history}
            genres = list(Libro.objects.filter(pk__in=ids).values_list('genero', flat=True))
            if genres:
                qs = qs.filter(genero__in=genres).exclude(pk__in=ids)
        return Response(self.get_serializer(qs[:10], many=True).data)

class InternalLibros(APIView):
    authentication_classes = []
    permission_classes = [InternalOnly]
    def post(self, request):
        ids = request.data.get('libro_ids', [])
        if not isinstance(ids, list) or len(ids)>1000:
            raise ValidationError('Máximo 1000 identificadores.')
        qs = Libro.objects.filter(id__in=ids).annotate(ocupados=Count('reserva', filter=Q(reserva__estado__in=['reservada','confirmada'])))
        return Response({str(book.id): LibroSerializer(book).data for book in qs})

class LegacyReserva(APIView):
    authentication_classes = []
    permission_classes = [InternalOnly]
    @transaction.atomic
    def post(self, request):
        if not settings.LEGACY_CATALOG_ENABLED:
            from rest_framework.exceptions import NotFound
            raise NotFound()
        from biblioteca_common.messaging import validate
        from .domain import handle
        try:
            validate(request.data)
            return Response(handle(request.data, publish=False))
        except (ValueError, KeyError, TypeError):
            raise ValidationError('Comando inválido.')

class LegacyReservas(APIView):
    authentication_classes = []
    permission_classes = [InternalOnly]
    def get(self, request):
        if not settings.LEGACY_CATALOG_ENABLED:
            from rest_framework.exceptions import NotFound
            raise NotFound()
        return Response(list(Reserva.objects.filter(estado__in=['reservada','confirmada']).values('prestamo_id','libro_id','estado')))

class InternalAsignaciones(APIView):
    authentication_classes = []
    permission_classes = [InternalOnly]
    def get(self, request):
        return Response(list(Reserva.objects.filter(estado__in=['reservada','confirmada']).values('prestamo_id','libro_id','estado')))
