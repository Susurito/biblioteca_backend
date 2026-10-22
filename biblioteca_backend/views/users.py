from django.shortcuts import get_object_or_404
from django.db import transaction
from rest_framework import generics, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from django.contrib.auth.models import Group
from django.contrib.auth import get_user_model
from biblioteca_backend.models import Administradores, Alumnos
from biblioteca_backend.serializers import AdminSerializer, UserSerializer, AlumnoSerializer

from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated

User = get_user_model()


# === Registro / Gestión de Usuarios ===
class UsuariosView(generics.CreateAPIView):
    permission_classes = (permissions.AllowAny,)  # Permitir registro público

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        email = request.data.get('email')
        nombre = request.data.get('nombre')
        apellido_paterno = request.data.get('apellido_paterno', '')
        apellido_materno = request.data.get('apellido_materno', '')
        password = request.data.get('password')
        tipo = request.data.get('tipo')
        matricula = request.data.get('matricula')

        if not all([email, nombre, password, tipo, matricula]):
            return Response({"error": "Todos los campos obligatorios deben estar completos"}, status=400)

        if User.objects.filter(email=email).exists():
            return Response({"error": f"Email {email} ya registrado"}, status=400)

        # Crear usuario
        user = User.objects.create(
            username=email,
            email=email,
            first_name=nombre,
            last_name=f"{apellido_paterno} {apellido_materno}".strip(),
            is_active=True
        )
        user.set_password(password)
        user.save()

        # Normalizar nombre de grupo
        tipo_normalizado = tipo.lower()
        if tipo_normalizado != "alumno":
            user.delete()
            return Response(
                {"error": "El registro público solo puede crear cuentas de Alumno. "
                          "Las cuentas de Administrador deben darlas de alta otro administrador autenticado."},
                status=403
            )

        # Crear o asignar grupo
        group, _ = Group.objects.get_or_create(name="alumno")
        group.user_set.add(user)

        # Crear registro de alumno
        alumno = Alumnos.objects.create(
            user=user,
            matricula=matricula,
            nombre=nombre,
            apellido_paterno=apellido_paterno,
            apellido_materno=apellido_materno
        )
        return Response({"id": alumno.id, "tipo": "Alumno"}, status=201)
        # # Normalizar nombre de grupo
        # tipo_normalizado = tipo.lower()
        # if tipo_normalizado not in ["alumno", "administrador"]:
        #     user.delete()
        #     return Response({"error": "Tipo de usuario no válido"}, status=400)

        # # Crear o asignar grupo
        # group, _ = Group.objects.get_or_create(name=tipo_normalizado)
        # group.user_set.add(user)

        # # Crear registro según tipo
        # if tipo_normalizado == "alumno":
        #     alumno = Alumnos.objects.create(
        #         user=user,
        #         matricula=matricula,
        #         nombre=nombre,
        #         apellido_paterno=apellido_paterno,
        #         apellido_materno=apellido_materno
        #     )
        #     return Response({"id": alumno.id, "tipo": "Alumno"}, status=201)

        # elif tipo_normalizado == "administrador":
        #     admin = Administradores.objects.create(
        #         user=user,
        #         matricula=matricula
        #     )
        #     return Response({"id": admin.id, "tipo": "Administrador"}, status=201)


# === Gestión de Administradores existentes ===
class AdminView(generics.CreateAPIView):
    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request, *args, **kwargs):
        admin_id = request.GET.get("id")
        if not admin_id:
            return Response({"error": "ID de administrador requerido"}, status=400)
        admin = get_object_or_404(Administradores, id=admin_id)
        data = AdminSerializer(admin).data
        return Response(data, 200)

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        email = request.data.get('email')
        first_name = request.data.get('first_name')
        last_name = request.data.get('last_name', '')
        password = request.data.get('password')
        rol = request.data.get('rol')
        matricula = request.data.get('matricula')

        if not all([email, first_name, password, rol, matricula]):
            return Response({"error": "Todos los campos son obligatorios"}, status=400)

        if User.objects.filter(email=email).exists():
            return Response({"error": f"Email {email} ya registrado"}, status=400)

        # Crear usuario
        user = User.objects.create(
            username=email,
            email=email,
            first_name=first_name,
            last_name=last_name,
            is_active=True
        )
        user.set_password(password)
        user.save()

        # Asignar grupo/rol
        rol_normalizado = rol.lower()
        group, _ = Group.objects.get_or_create(name=rol_normalizado)
        group.user_set.add(user)

        # Crear registro de administrador
        admin = Administradores.objects.create(
            user=user,
            matricula=matricula
        )

        return Response({"admin_created_id": admin.id}, status=201)


class PerfilUsuarioView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        perfil = {}

        # Verificar si es alumno
        if user.groups.filter(name="Alumno").exists():
            alumno = Alumnos.objects.get(user=user)
            from biblioteca_backend.views.views import verificar_bloqueo_alumno
            bloqueado, motivo, fecha_desbloqueo = verificar_bloqueo_alumno(alumno)
            perfil = {
                "id": alumno.id,
                "alumno_id": alumno.id,
                "nombre": alumno.nombre,
                "apellido_paterno": alumno.apellido_paterno,
                "apellido_materno": alumno.apellido_materno,
                "email": user.email,
                "matricula": alumno.matricula,
                "rol": "Alumno",
                "bloqueado": bloqueado,
                "bloqueo_motivo": motivo,
                "bloqueo_hasta": fecha_desbloqueo
            }

        # Verificar si es administrador
        elif user.groups.filter(name="Administrador").exists():
            admin = Administradores.objects.get(user=user)
            perfil = {
                "email": user.email,
                "matricula": admin.matricula,
                "rol": "Administrador"
            }

        return Response(perfil)


def format_usuario_data(user):
    from biblioteca_backend.views.views import verificar_bloqueo_alumno
    from biblioteca_backend.models import Prestamos, Alumnos, Administradores
    from django.utils import timezone
    from datetime import timedelta

    alumno = Alumnos.objects.filter(user=user).first()
    admin = Administradores.objects.filter(user=user).first()
    ahora = timezone.now()

    if alumno:
        bloqueado, bloqueo_motivo, bloqueo_hasta = verificar_bloqueo_alumno(alumno)
        prestamos_activos_count = Prestamos.objects.filter(alumno=alumno, devuelto=False, estado='aceptado').count()
        rol = getattr(alumno, 'rol', 'Estudiante') or 'Estudiante'
        limite = 5 if rol.lower() == 'docente' else 3
        matricula = alumno.matricula
        nombre = alumno.nombre
        apellido_paterno = alumno.apellido_paterno
        apellido_materno = alumno.apellido_materno
        nombre_completo = f"{nombre} {apellido_paterno} {apellido_materno}".strip()
        tipo_modelo = 'alumno'
        modelo_id = alumno.id

        # Sanciones e historial de multas
        sanciones = []
        multas_pendientes = 0.0

        prestamos_devueltos = Prestamos.objects.filter(
            alumno=alumno,
            devuelto=True,
            fecha_devolucion__isnull=False,
            fecha_vencimiento__isnull=False
        ).order_by('-fecha_devolucion')

        for p in prestamos_devueltos:
            if p.fecha_devolucion.date() > p.fecha_vencimiento.date():
                dias = (p.fecha_devolucion.date() - p.fecha_vencimiento.date()).days
                if dias > 0:
                    monto = dias * 5.0
                    pagada = getattr(p, 'multa_pagada', False)
                    if not pagada:
                        multas_pendientes += monto

                    fecha_fin_bloq = None
                    if dias > 7:
                        fecha_fin_bloq = (p.fecha_devolucion + timedelta(days=15)).strftime('%d/%m/%Y')

                    sanciones.append({
                        "prestamo_id": p.id,
                        "libro_titulo": p.libro.titulo,
                        "libro_autor": p.libro.autor,
                        "fecha_prestamo": p.fecha_solicitud.strftime('%d/%m/%Y') if p.fecha_solicitud else "-",
                        "fecha_vencimiento": p.fecha_vencimiento.strftime('%d/%m/%Y') if p.fecha_vencimiento else "-",
                        "fecha_devolucion": p.fecha_devolucion.strftime('%d/%m/%Y') if p.fecha_devolucion else "-",
                        "dias_retraso": dias,
                        "monto_multa": monto,
                        "multa_formateada": f"${monto:.2f} MXN",
                        "pagada": pagada,
                        "fecha_pago": p.fecha_pago_multa.strftime('%d/%m/%Y') if getattr(p, 'fecha_pago_multa', None) else None,
                        "es_rn04": dias > 7,
                        "bloqueo_hasta": fecha_fin_bloq,
                        "motivo": f"Retraso de {dias} días (RN-04: Suspensión de 15 días)" if dias > 7 else f"Retraso de {dias} días (RN-03: Multa sin suspensión)"
                    })

        # Préstamos activos con retraso actual
        prestamos_activos_vencidos = Prestamos.objects.filter(
            alumno=alumno,
            devuelto=False,
            estado='aceptado'
        )
        for p in prestamos_activos_vencidos:
            fv = p.fecha_vencimiento or (p.fecha_solicitud + timedelta(days=7) if p.fecha_solicitud else None)
            if fv and ahora.date() > fv.date():
                dias = (ahora.date() - fv.date()).days
                if dias > 0:
                    monto = dias * 5.0
                    multas_pendientes += monto
                    sanciones.append({
                        "prestamo_id": p.id,
                        "libro_titulo": p.libro.titulo,
                        "libro_autor": p.libro.autor,
                        "fecha_prestamo": p.fecha_solicitud.strftime('%d/%m/%Y') if p.fecha_solicitud else "-",
                        "fecha_vencimiento": fv.strftime('%d/%m/%Y'),
                        "fecha_devolucion": "En curso (No devuelto)",
                        "dias_retraso": dias,
                        "monto_multa": monto,
                        "multa_formateada": f"${monto:.2f} MXN",
                        "pagada": False,
                        "fecha_pago": None,
                        "es_rn04": dias > 7,
                        "bloqueo_hasta": (ahora + timedelta(days=15)).strftime('%d/%m/%Y') if dias > 7 else None,
                        "motivo": f"Libro en posesión con {dias} días de retraso"
                    })

    elif admin:
        bloqueado = False
        bloqueo_motivo = ""
        bloqueo_hasta = None
        prestamos_activos_count = 0
        rol = 'Bibliotecario'
        limite = 5
        matricula = admin.matricula
        nombre = user.first_name
        apellido_paterno = user.last_name
        apellido_materno = ""
        nombre_completo = f"{nombre} {apellido_paterno}".strip() or user.username
        tipo_modelo = 'admin'
        modelo_id = admin.id
        sanciones = []
        multas_pendientes = 0.0
    else:
        bloqueado = False
        bloqueo_motivo = ""
        bloqueo_hasta = None
        prestamos_activos_count = 0
        rol = 'Estudiante'
        limite = 3
        matricula = getattr(user, 'username', '')
        nombre = user.first_name
        apellido_paterno = user.last_name
        apellido_materno = ""
        nombre_completo = f"{nombre} {apellido_paterno}".strip() or user.username
        tipo_modelo = 'user'
        modelo_id = user.id
        sanciones = []
        multas_pendientes = 0.0

    if not user.is_active:
        estado_label = 'Inactivo'
    elif bloqueado:
        if bloqueo_hasta:
            partes = bloqueo_hasta.split('/')
            if len(partes) >= 2:
                estado_label = f"Bloqueado hasta {partes[0]}/{partes[1]}"
            else:
                estado_label = f"Bloqueado hasta {bloqueo_hasta}"
        else:
            estado_label = "Bloqueado"
    else:
        estado_label = 'Activo'

    return {
        "id": user.id,
        "user_id": user.id,
        "modelo_id": modelo_id,
        "tipo_modelo": tipo_modelo,
        "email": user.email or user.username,
        "username": user.username,
        "nombre": nombre,
        "apellido_paterno": apellido_paterno,
        "apellido_materno": apellido_materno,
        "nombre_completo": nombre_completo,
        "matricula": matricula,
        "rol": rol,
        "is_active": user.is_active,
        "prestamos_activos": prestamos_activos_count,
        "limite_prestamos": limite,
        "prestamos_display": f"{prestamos_activos_count} / {limite}",
        "bloqueado": bloqueado,
        "bloqueo_motivo": bloqueo_motivo,
        "bloqueo_hasta": bloqueo_hasta,
        "estado": estado_label,
        "multas_pendientes": multas_pendientes,
        "multas_display": f"${multas_pendientes:.2f} MXN",
        "sanciones": sanciones
    }


class UsuariosViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]

    def _es_admin(self, user):
        if not user or not user.is_authenticated:
            return False
        return (
            user.is_superuser or
            user.groups.filter(name__iexact="Administrador").exists() or
            user.groups.filter(name__iexact="admin").exists() or
            user.groups.filter(name__iexact="administradores").exists() or
            Administradores.objects.filter(user=user).exists()
        )

    def list(self, request):
        if not self._es_admin(request.user):
            return Response({"error": "Acceso restringido a Administradores."}, status=status.HTTP_403_FORBIDDEN)

        users = User.objects.all().order_by('id')
        data = [format_usuario_data(u) for u in users]
        return Response(data, status=status.HTTP_200_OK)

    def retrieve(self, request, pk=None):
        if not self._es_admin(request.user):
            return Response({"error": "Acceso restringido a Administradores."}, status=status.HTTP_403_FORBIDDEN)

        user = get_object_or_404(User, id=pk)
        return Response(format_usuario_data(user), status=status.HTTP_200_OK)

    @transaction.atomic
    def create(self, request):
        if not self._es_admin(request.user):
            return Response({"error": "Acceso restringido a Administradores."}, status=status.HTTP_403_FORBIDDEN)

        email = request.data.get('email')
        nombre = request.data.get('nombre')
        apellido_paterno = request.data.get('apellido_paterno', '')
        apellido_materno = request.data.get('apellido_materno', '')
        matricula = request.data.get('matricula')
        rol = request.data.get('rol', 'Estudiante')
        password = request.data.get('password', '123456')

        if not all([email, nombre, matricula, rol]):
            return Response({"error": "Faltan campos obligatorios: email, nombre, matricula, rol."}, status=status.HTTP_400_BAD_REQUEST)

        if User.objects.filter(email=email).exists() or User.objects.filter(username=email).exists():
            return Response({"error": f"El correo {email} ya se encuentra registrado."}, status=status.HTTP_400_BAD_REQUEST)

        if Alumnos.objects.filter(matricula=matricula).exists() or Administradores.objects.filter(matricula=matricula).exists():
            return Response({"error": f"La matrícula {matricula} ya está en uso."}, status=status.HTTP_400_BAD_REQUEST)

        user = User.objects.create_user(
            username=email,
            email=email,
            first_name=nombre,
            last_name=f"{apellido_paterno} {apellido_materno}".strip(),
            is_active=True
        )
        user.set_password(password)
        user.save()

        rol_norm = rol.lower().strip()
        if rol_norm in ['bibliotecario', 'administrador', 'admin']:
            group, _ = Group.objects.get_or_create(name='administrador')
            group.user_set.add(user)
            admin = Administradores.objects.create(
                user=user,
                matricula=matricula
            )
        else:
            group, _ = Group.objects.get_or_create(name='alumno')
            group.user_set.add(user)
            alumno = Alumnos.objects.create(
                user=user,
                matricula=matricula,
                nombre=nombre,
                apellido_paterno=apellido_paterno,
                apellido_materno=apellido_materno,
                rol=rol
            )

        return Response(format_usuario_data(user), status=status.HTTP_201_CREATED)

    @transaction.atomic
    def update(self, request, pk=None):
        if not self._es_admin(request.user):
            return Response({"error": "Acceso restringido a Administradores."}, status=status.HTTP_403_FORBIDDEN)

        user = get_object_or_404(User, id=pk)
        email = request.data.get('email')
        nombre = request.data.get('nombre')
        apellido_paterno = request.data.get('apellido_paterno', '')
        apellido_materno = request.data.get('apellido_materno', '')
        matricula = request.data.get('matricula')
        rol = request.data.get('rol')
        password = request.data.get('password')

        if email and email != user.email:
            if User.objects.filter(email=email).exclude(id=user.id).exists():
                return Response({"error": f"El correo {email} ya está registrado por otro usuario."}, status=status.HTTP_400_BAD_REQUEST)
            user.email = email
            user.username = email

        if nombre:
            user.first_name = nombre
        if apellido_paterno or apellido_materno:
            user.last_name = f"{apellido_paterno} {apellido_materno}".strip()
        if password:
            user.set_password(password)
        user.save()

        alumno = Alumnos.objects.filter(user=user).first()
        admin = Administradores.objects.filter(user=user).first()

        if alumno:
            if nombre:
                alumno.nombre = nombre
            if apellido_paterno:
                alumno.apellido_paterno = apellido_paterno
            if apellido_materno is not None:
                alumno.apellido_materno = apellido_materno
            if matricula:
                alumno.matricula = matricula
            if rol:
                alumno.rol = rol
            alumno.save()
        elif admin:
            if matricula:
                admin.matricula = matricula
            admin.save()

        return Response(format_usuario_data(user), status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='desactivar')
    def desactivar(self, request, pk=None):
        if not self._es_admin(request.user):
            return Response({"error": "Acceso restringido a Administradores."}, status=status.HTTP_403_FORBIDDEN)

        user = get_object_or_404(User, id=pk)
        user.is_active = False
        user.save()
        return Response({
            "message": f"Usuario '{user.email}' desactivado exitosamente.",
            "usuario": format_usuario_data(user)
        }, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='reactivar')
    def reactivar(self, request, pk=None):
        if not self._es_admin(request.user):
            return Response({"error": "Acceso restringido a Administradores."}, status=status.HTTP_403_FORBIDDEN)

        user = get_object_or_404(User, id=pk)
        user.is_active = True
        user.save()
        return Response({
            "message": f"Usuario '{user.email}' reactivado exitosamente.",
            "usuario": format_usuario_data(user)
        }, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='pagar-multa')
    def pagar_multa(self, request, pk=None):
        if not self._es_admin(request.user):
            return Response({"error": "Acceso restringido a Administradores."}, status=status.HTTP_403_FORBIDDEN)

        from biblioteca_backend.models import Prestamos, Alumnos
        from django.utils import timezone

        user = get_object_or_404(User, id=pk)
        alumno = Alumnos.objects.filter(user=user).first()
        if not alumno:
            return Response({"error": "El usuario no es un alumno con multas aplicables."}, status=status.HTTP_400_BAD_REQUEST)

        prestamo_id = request.data.get('prestamo_id')
        ahora = timezone.now()

        if prestamo_id:
            prestamos_a_pagar = Prestamos.objects.filter(id=prestamo_id, alumno=alumno)
        else:
            prestamos_a_pagar = Prestamos.objects.filter(alumno=alumno, devuelto=True, multa_pagada=False)

        count = 0
        total_pagado = 0.0
        for p in prestamos_a_pagar:
            if p.fecha_devolucion and p.fecha_vencimiento and p.fecha_devolucion.date() > p.fecha_vencimiento.date():
                dias = (p.fecha_devolucion.date() - p.fecha_vencimiento.date()).days
                total_pagado += dias * 5.0
            p.multa_pagada = True
            p.fecha_pago_multa = ahora
            p.save()
            count += 1

        return Response({
            "message": f"Pago registrado exitosamente. Se saldaron {count} multas por un total de ${total_pagado:.2f} MXN.",
            "total_pagado": f"${total_pagado:.2f} MXN",
            "usuario": format_usuario_data(user)
        }, status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'], url_path='ficha')
    def ficha(self, request, pk=None):
        if not self._es_admin(request.user):
            return Response({"error": "Acceso restringido a Administradores."}, status=status.HTTP_403_FORBIDDEN)

        user = get_object_or_404(User, id=pk)
        data = format_usuario_data(user)

        # Agregar préstamos detallados para la ficha
        alumno = Alumnos.objects.filter(user=user).first()
        prestamos_lista = []
        if alumno:
            from biblioteca_backend.models import Prestamos
            for p in Prestamos.objects.filter(alumno=alumno).order_by('-fecha_solicitud'):
                prestamos_lista.append({
                    "id": p.id,
                    "libro_titulo": p.libro.titulo,
                    "libro_autor": p.libro.autor,
                    "fecha_solicitud": p.fecha_solicitud.strftime('%d/%m/%Y') if p.fecha_solicitud else "-",
                    "fecha_vencimiento": p.fecha_vencimiento.strftime('%d/%m/%Y') if p.fecha_vencimiento else "-",
                    "fecha_devolucion": p.fecha_devolucion.strftime('%d/%m/%Y') if p.fecha_devolucion else "-",
                    "devuelto": p.devuelto,
                    "estado": p.estado
                })
        data['historial_prestamos'] = prestamos_lista
        return Response(data, status=status.HTTP_200_OK)