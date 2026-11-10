"""Temporary Strangler adapters. Identity is authoritative; local users are projections."""
import uuid
from datetime import timedelta
from django.conf import settings
from django.db import transaction
from django.contrib.auth.models import User, Group
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.exceptions import AuthenticationFailed, ValidationError
from biblioteca_common.auth import RemoteTokenAuthentication, InternalOnly
from biblioteca_common.http import call
from .models import Alumnos, Administradores, Prestamos, Libros

class IdentityAuthentication(RemoteTokenAuthentication):
    @transaction.atomic
    def authenticate(self, request):
        resolved=super().authenticate(request)
        if not resolved:
            return None
        principal, token=resolved
        data=call(settings.IDENTITY_URL, '/internal/usuarios/'+str(principal.id)+'/')
        user,created=User.objects.get_or_create(pk=principal.id, defaults={'username':data['username']})
        user.username=data['username']
        user.email=data['email']
        user.first_name=data['nombre']
        user.last_name=data['apellido_paterno']
        user.is_active=data['is_active']
        user.is_superuser=principal.is_superuser
        # Only unusable passwords remain in the compatibility projection.
        user.set_unusable_password()
        user.save()
        group,_=Group.objects.get_or_create(name=principal.rol)
        user.groups.set([group])
        if data.get('alumno_id'):
            Alumnos.objects.update_or_create(pk=data['alumno_id'], defaults={
                'user':user, 'matricula':data['matricula'], 'nombre':data['nombre'],
                'apellido_paterno':data['apellido_paterno'], 'apellido_materno':data['apellido_materno'],
                'rol':data.get('rol_academico') or 'Estudiante'})
        elif data.get('admin_id'):
            Administradores.objects.update_or_create(pk=data['admin_id'],defaults={'user':user,'matricula':data['matricula']})
        return user,token

class Resumenes(APIView):
    authentication_classes=[]
    permission_classes=[InternalOnly]
    def post(self,request):
        from .views.users import format_usuario_data
        from .serializers import PrestamosSerializer
        ids=request.data.get('alumno_ids',[])
        if not isinstance(ids,list) or len(ids)>1000:
            raise ValidationError('Máximo 1000 identificadores.')
        result={}
        for alumno in Alumnos.objects.filter(pk__in=ids).select_related('user'):
            data=format_usuario_data(alumno.user)
            data['historial_prestamos']=PrestamosSerializer(Prestamos.objects.filter(alumno=alumno),many=True).data
            result[str(alumno.pk)]={k:data[k] for k in ('bloqueado','bloqueo_motivo','bloqueo_hasta',
                'prestamos_activos','limite_prestamos','multas_pendientes','multas_display','sanciones','historial_prestamos')}
        # A student registered in identity has no old loans until first request.
        for aid in ids:
            result.setdefault(str(aid),dict(bloqueado=False,bloqueo_motivo='',bloqueo_hasta=None,
                prestamos_activos=0,limite_prestamos=3,multas_pendientes=0,multas_display='$0.00 MXN',sanciones=[],historial_prestamos=[]))
        return Response(result)

class Historial(APIView):
    authentication_classes=[]
    permission_classes=[InternalOnly]
    def post(self,request):
        from .serializers import PrestamosSerializer
        aid=request.data.get('alumno_id')
        if not aid:
            raise ValidationError('alumno_id requerido.')
        return Response(PrestamosSerializer(Prestamos.objects.filter(alumno_id=aid),many=True).data)

class Pago(APIView):
    authentication_classes=[]
    permission_classes=[InternalOnly]
    @transaction.atomic
    def post(self,request):
        from decimal import Decimal
        aid=request.data.get('alumno_id')
        if not aid:
            raise ValidationError('alumno_id requerido.')
        qs=Prestamos.objects.select_for_update().filter(alumno_id=aid,devuelto=True,multa_pagada=False)
        if request.data.get('prestamo_id'):
            qs=qs.filter(pk=request.data['prestamo_id'])
        total,count=Decimal('0'),0
        for p in qs:
            if not p.fecha_vencimiento or not p.fecha_devolucion:
                continue
            days=max(0,(timezone.localtime(p.fecha_devolucion).date()-timezone.localtime(p.fecha_vencimiento).date()).days)
            if not days:
                continue
            total+=Decimal(days)*5
            p.multa_pagada=True
            p.fecha_pago_multa=timezone.now()
            p.save(update_fields=['multa_pagada','fecha_pago_multa'])
            count+=1
        return Response({'message':f'Se saldaron {count} multas.', 'total_pagado':f'${total:.2f} MXN'})


def catalog_command(loan,kind):
    sid=str(uuid.uuid5(uuid.NAMESPACE_URL,'biblioteca:legacy-loan:'+str(loan.pk)))
    return call(settings.BOOKS_URL,'/internal/legacy-reserva/',dict(
        message_id=str(uuid.uuid4()),saga_id=sid,version=1,type=kind,
        payload={'prestamo_id':loan.pk,'libro_id':loan.libro_id,'reserva_saga_id':sid}))


def project_book(bid):
    data=call(settings.BOOKS_URL,'/internal/libros/',{'libro_ids':[bid]}).get(str(bid))
    if not data:
        raise ValidationError('Libro inexistente.')
    fields={k:data[k] for k in ('isbn','titulo','autor','genero','detalles','total_ejemplares','baja','disponible')}
    book,_=Libros.objects.update_or_create(pk=bid,defaults=fields)
    return book


@transaction.atomic
def legacy_action(pid,kind):
    from .views.views import verificar_bloqueo_alumno
    # Lock the student's row before the loan, across every approval/return path.
    preview=Prestamos.objects.get(pk=pid)
    Alumnos.objects.select_for_update().get(pk=preview.alumno_id)
    p=Prestamos.objects.select_for_update().get(pk=pid)
    if kind=='aprobar':
        if p.estado=='aceptado':
            return {'message':'Préstamo ya aprobado.'}
        if p.estado!='pendiente' or p.devuelto:
            raise ValidationError('Solo se aprueban solicitudes pendientes.')
        if getattr(settings, 'IDENTITY_AUTH_ENABLED', False):
            remote=call(settings.IDENTITY_URL,'/internal/alumnos/',{'alumno_ids':[p.alumno_id]}).get(str(p.alumno_id))
            if not remote or not remote['is_active']:
                raise ValidationError('Alumno inactivo.')
        blocked,reason,_=verificar_bloqueo_alumno(p.alumno)
        if blocked:
            raise ValidationError(reason)
        if Prestamos.objects.filter(alumno=p.alumno,estado='aceptado',devuelto=False).count()>=3:
            raise ValidationError('Límite de tres préstamos.')
        result=catalog_command(p,'ReservarEjemplar')
        if result['type']!='EjemplarReservado':
            raise ValidationError('Sin existencias. Rechaza esta solicitud y crea una nueva.')
        result=catalog_command(p,'ConfirmarReserva')
        if result['type']!='ReservaConfirmada':
            raise ValidationError('Reserva no confirmada.')
        p.estado='aceptado'
        p.fecha_solicitud=timezone.now()
        p.fecha_vencimiento=p.fecha_solicitud+timedelta(days=7)
        p.save()
        return {'message':'Préstamo aprobado.'}
    if kind=='rechazar':
        if p.estado=='aceptado' or p.devuelto:
            raise ValidationError('No se rechaza un préstamo aprobado.')
        catalog_command(p,'LiberarReserva')
        p.estado='rechazado'
        p.save(update_fields=['estado'])
        return {'message':'Solicitud rechazada.'}
    if kind=='devolver':
        if p.estado!='aceptado':
            raise ValidationError('Solo se devuelven préstamos activos.')
        # Release is idempotent: retry after a failed local commit safely repeats it.
        result=catalog_command(p,'LiberarReserva')
        if not p.devuelto:
            p.devuelto=True
            p.fecha_devolucion=timezone.now()
            p.save(update_fields=['devuelto','fecha_devolucion'])
        days=max(0,(timezone.localtime(p.fecha_devolucion).date()-timezone.localtime(p.fecha_vencimiento).date()).days) if p.fecha_vencimiento else 0
        payload=result['payload']
        fmt=lambda dt: timezone.localtime(dt).strftime('%d/%m/%Y') if dt else '-'
        details=dict(id=p.pk,alumno_nombre=p.alumno.nombre,
            alumno_nombre_completo=' '.join((p.alumno.nombre,p.alumno.apellido_paterno,p.alumno.apellido_materno)).strip(),
            libro_titulo=p.libro.titulo,libro_autor=p.libro.autor,
            fecha_vencimiento=fmt(p.fecha_vencimiento),fecha_devolucion=fmt(p.fecha_devolucion),
            dias_retraso=days,multa=f'${days*5:.2f} MXN',
            bloqueo='Hasta el '+fmt(p.fecha_devolucion+timedelta(days=15)) if days>7 else '------',
            mensaje_sancion='RN-04: multa y suspensión de 15 días.' if days>7 else 'RN-03: multa sin suspensión.' if days else 'Devolución a tiempo, sin sanción',
            stock_total=payload['stock_total'],stock_disponibles=payload['stock_disponibles'],
            stock_mensaje=f"Stock actualizado: {payload['stock_disponibles']} de {payload['stock_total']} disponibles.")
        return {'message':'Devolución registrada.','detalles_devolucion':details}
    raise ValidationError('Acción inválida.')
