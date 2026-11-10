from decimal import Decimal
from datetime import timedelta
from django.conf import settings
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError, PermissionDenied
from biblioteca_common.auth import IsAdmin, InternalOnly
from biblioteca_common.http import call
from .models import Prestamo, Saga
from .domain import approve, reject, return_loan, lock_student, eligibility, student
from .rules import late_days, fine, blocking

class PrestamoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Prestamo
        fields = ['id','fecha_solicitud','fecha_vencimiento','fecha_devolucion','devuelto','estado','multa_pagada','fecha_pago_multa']
    def to_representation(self, p):
        data = super().to_representation(p)
        a, b = p.alumno_snapshot, p.libro_snapshot
        data.update(alumno=p.alumno_id, user_id=p.user_id, libro=p.libro_id,
                    alumno_nombre=a.get('nombre',''), alumno_nombre_completo=a.get('nombre_completo',''),
                    alumno_matricula=a.get('matricula',''), libro_titulo=b.get('titulo',''),
                    libro_autor=b.get('autor',''), libro_isbn=b.get('isbn'),
                    es_vencido=not p.devuelto and p.estado=='aceptado' and late_days(p)>0,
                    dias_vencido=late_days(p))
        return data


def summary(rows):
    blocked, reason, until = blocking(rows)
    active = sum(p.estado=='aceptado' and not p.devuelto for p in rows)
    sanctions, pending = [], Decimal('0')
    for p in rows:
        days = late_days(p)
        if p.estado != 'aceptado' or days == 0:
            continue
        amount = fine(p)
        if not p.multa_pagada:
            pending += amount
        end = p.fecha_devolucion+timedelta(days=15) if p.devuelto and days>7 else None
        fmt = lambda dt: timezone.localtime(dt).strftime('%d/%m/%Y') if dt else '-'
        sanctions.append(dict(prestamo_id=p.pk, libro_titulo=p.libro_snapshot.get('titulo',''),
            libro_autor=p.libro_snapshot.get('autor',''), fecha_prestamo=fmt(p.fecha_solicitud),
            fecha_vencimiento=fmt(p.fecha_vencimiento), fecha_devolucion=fmt(p.fecha_devolucion) if p.devuelto else 'En curso (No devuelto)',
            dias_retraso=days, monto_multa=float(amount), multa_formateada=f'${amount:.2f} MXN',
            pagada=p.multa_pagada, fecha_pago=fmt(p.fecha_pago_multa) if p.fecha_pago_multa else None,
            es_rn04=days>7, bloqueo_hasta=fmt(end) if end else None,
            motivo='RN-04: multa y suspensión' if days>7 else 'RN-03: multa sin suspensión'))
    return dict(bloqueado=blocked, bloqueo_motivo=reason, bloqueo_hasta=until,
                prestamos_activos=active, limite_prestamos=3, multas_pendientes=float(pending),
                multas_display=f'${pending:.2f} MXN', sanciones=sanctions,
                historial_prestamos=PrestamoSerializer(rows, many=True).data)


def operation(saga):
    return dict(operacion_id=str(saga.pk), estado=saga.estado, prestamo_id=saga.prestamo_id,
                error=saga.error or None, resultado=saga.resultado,
                message='Operación completada.' if saga.estado=='completada' else 'Operación en proceso.')

class PrestamosViewSet(viewsets.GenericViewSet):
    serializer_class = PrestamoSerializer
    def get_queryset(self):
        qs = Prestamo.objects.all().order_by('devuelto','-id')
        if not IsAdmin().has_permission(self.request, self):
            qs = qs.filter(user_id=self.request.user.id)
        return qs
    def list(self, request):
        page = self.paginate_queryset(self.get_queryset())
        return self.get_paginated_response(self.get_serializer(page, many=True).data)
    def retrieve(self, request, pk=None):
        return Response(self.get_serializer(self.get_object()).data)
    @transaction.atomic
    def create(self, request):
        aid = getattr(request.user, 'alumno_id', None)
        if not aid:
            raise PermissionDenied('Solo los alumnos solicitan préstamos.')
        alumno = student(aid)
        book_id = serializers.IntegerField(min_value=1).run_validation(request.data.get('libro'))
        book = call(settings.BOOKS_URL, '/internal/libros/', {'libro_ids':[book_id]}).get(str(book_id))
        if not book or not book['disponible']:
            raise ValidationError({'error':'Libro inexistente o sin disponibilidad.'})
        lock_student(aid)
        eligibility(aid)
        if Prestamo.objects.filter(alumno_id=aid, libro_id=book_id, devuelto=False).exclude(estado='rechazado').exists():
            raise ValidationError({'error':'Ya existe una solicitud pendiente o activa para este libro.'})
        p = Prestamo.objects.create(alumno_id=aid, user_id=request.user.id, libro_id=book_id,
                                    alumno_snapshot=alumno, libro_snapshot=book)
        return Response(self.get_serializer(p).data, status=201)
    def require_admin(self, request):
        if not IsAdmin().has_permission(request, self):
            raise PermissionDenied('Solo administradores.')
    @action(detail=True, methods=['post'])
    def aprobar(self, request, pk=None):
        self.require_admin(request)
        return Response(operation(approve(self.get_object().pk)), status=202)
    @action(detail=True, methods=['post'])
    def rechazar(self, request, pk=None):
        self.require_admin(request)
        saga = reject(self.get_object().pk)
        return Response(operation(saga), status=202) if saga else Response({'message':'Solicitud rechazada.'})
    @action(detail=True, methods=['post'])
    def devolver(self, request, pk=None):
        self.require_admin(request)
        return Response(operation(return_loan(self.get_object().pk)), status=202)
    def partial_update(self, request, pk=None):
        if request.data != {'devuelto': True}:
            raise ValidationError('Usa las acciones explícitas del préstamo.')
        return self.devolver(request, pk)
    @action(detail=True, methods=['post'])
    def revisar(self, request, pk=None):
        act = request.data.get('accion')
        if act not in ('aprobar','rechazar'):
            raise ValidationError('Acción inválida.')
        return self.aprobar(request, pk) if act=='aprobar' else self.rechazar(request, pk)
    @action(detail=False, methods=['get'])
    def estadisticas(self, request):
        self.require_admin(request)
        qs = list(self.get_queryset())
        return Response(dict(total=len(qs), por_aprobar=sum(p.estado=='pendiente' and not p.devuelto for p in qs),
             activos=sum(p.estado=='aceptado' and not p.devuelto for p in qs),
             vencidos=sum(p.estado=='aceptado' and not p.devuelto and late_days(p)>0 for p in qs),
             historial=sum(p.devuelto or p.estado=='rechazado' for p in qs)))

class OperacionView(APIView):
    def get(self, request, pk):
        saga = get_object_or_404(Saga.objects.select_related('prestamo'), pk=pk)
        if saga.prestamo.user_id != request.user.id and not IsAdmin().has_permission(request,self):
            raise PermissionDenied()
        return Response(operation(saga))

class InternalResumenes(APIView):
    authentication_classes = []
    permission_classes = [InternalOnly]
    def post(self, request):
        ids = request.data.get('alumno_ids', [])
        if not isinstance(ids,list) or len(ids)>1000:
            raise ValidationError('Máximo 1000 identificadores.')
        groups = {str(aid):[] for aid in ids}
        for p in Prestamo.objects.filter(alumno_id__in=ids).order_by('-id'):
            groups[str(p.alumno_id)].append(p)
        return Response({aid:summary(rows) for aid,rows in groups.items()})

class InternalHistorial(APIView):
    authentication_classes = []
    permission_classes = [InternalOnly]
    def post(self, request):
        aid = serializers.IntegerField(min_value=1).run_validation(request.data.get('alumno_id'))
        return Response(PrestamoSerializer(Prestamo.objects.filter(alumno_id=aid).order_by('-id'), many=True).data)

class InternalPago(APIView):
    authentication_classes = []
    permission_classes = [InternalOnly]
    @transaction.atomic
    def post(self, request):
        aid = serializers.IntegerField(min_value=1).run_validation(request.data.get('alumno_id'))
        lock_student(aid)
        qs = Prestamo.objects.select_for_update().filter(alumno_id=aid, devuelto=True, multa_pagada=False)
        if request.data.get('prestamo_id'):
            qs = qs.filter(pk=serializers.IntegerField(min_value=1).run_validation(request.data['prestamo_id']))
        count, total = 0, Decimal('0')
        for p in qs:
            amount = fine(p)
            if amount<=0:
                continue
            total += amount
            p.multa_pagada, p.fecha_pago_multa = True, timezone.now()
            p.save(update_fields=['multa_pagada','fecha_pago_multa'])
            count += 1
        return Response({'message':f'Se saldaron {count} multas por ${total:.2f} MXN.', 'total_pagado':f'${total:.2f} MXN'})
