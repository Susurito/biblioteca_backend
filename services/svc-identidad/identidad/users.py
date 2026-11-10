"""Dominio de identidad: cuentas, roles, alumnos y administradores."""

from django.db import transaction
from django.conf import settings
from rest_framework.exceptions import ValidationError
from rest_framework import serializers
from biblioteca_common.http import call, DependencyUnavailable
from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from rest_framework import generics, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from identidad.models import Administradores, Alumnos
from identidad.serializers import AdminSerializer, AlumnoSerializer, UserSerializer

User = get_user_model()

def validate_input(data, creating=True):
    if creating or data.get('email'):
        serializers.EmailField().run_validation(data.get('email'))
    if creating:
        serializers.CharField(max_length=10,allow_blank=False).run_validation(data.get('matricula'))
        serializers.CharField(min_length=6,trim_whitespace=False).run_validation(data.get('password'))
    elif data.get('password'):
        serializers.CharField(min_length=6,trim_whitespace=False).run_validation(data['password'])



def _es_admin(user) -> bool:
    """Verifica si el usuario tiene rol de administrador."""
    if not user or not user.is_authenticated:
        return False
    return (
        user.is_superuser or
        user.groups.filter(name__iexact="administrador").exists() or
        user.groups.filter(name__iexact="admin").exists() or
        Administradores.objects.filter(user=user).exists()
    )


def basic_usuario_data(user):
    alumno = Alumnos.objects.filter(user=user).first()
    admin = Administradores.objects.filter(user=user).first()
    data = {
        "id": user.id, "user_id": user.id,
        "alumno_id": alumno.id if alumno else None,
        "admin_id": admin.id if admin else None,
        "modelo_id": alumno.id if alumno else admin.id if admin else user.id,
        "tipo_modelo": "alumno" if alumno else "admin" if admin else "user",
        "email": user.email, "username": user.username,
        "nombre": alumno.nombre if alumno else user.first_name,
        "apellido_paterno": alumno.apellido_paterno if alumno else user.last_name,
        "apellido_materno": alumno.apellido_materno if alumno else "",
        "matricula": alumno.matricula if alumno else admin.matricula if admin else user.username,
        "rol": "administrador" if _es_admin(user) else "alumno",
        "rol_academico": alumno.rol if alumno else None,
        "is_active": user.is_active,
    }
    data['nombre_completo'] = ' '.join(data[k] for k in ('nombre', 'apellido_paterno', 'apellido_materno')).strip()
    return data


def enrich(rows):
    ids = [row['alumno_id'] for row in rows if row['alumno_id']]
    summaries = {}
    for offset in range(0, len(ids), 1000):
        summaries.update(call(settings.LOANS_URL, '/internal/resumenes/', {'alumno_ids': ids[offset:offset+1000]}))
    for row in rows:
        if row['alumno_id']:
            summary = summaries.get(str(row['alumno_id']))
            if summary is None:
                raise DependencyUnavailable('Resumen de préstamos incompleto.')
            row.update(summary)
        else:
            row.update(bloqueado=False, bloqueo_motivo='', bloqueo_hasta=None,
                       prestamos_activos=0, limite_prestamos=3, multas_pendientes=0,
                       multas_display='$0.00 MXN', sanciones=[], historial_prestamos=[])
        row['prestamos_display'] = f"{row['prestamos_activos']} / {row['limite_prestamos']}"
        row['estado'] = 'Inactivo' if not row['is_active'] else 'Bloqueado' if row['bloqueado'] else 'Activo'
    return rows


def format_usuario_data(user):
    return enrich([basic_usuario_data(user)])[0]


class AdminOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        return _es_admin(request.user)


# ─────────────────────────────────────────────────────────────
# Registro público
# ─────────────────────────────────────────────────────────────

class UsuariosView(generics.CreateAPIView):
    """POST /register/ — Registro público (solo alumnos)."""
    permission_classes = (permissions.AllowAny,)

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        validate_input(request.data)
        email = request.data.get('email')
        nombre = request.data.get('nombre')
        apellido_paterno = request.data.get('apellido_paterno', '')
        apellido_materno = request.data.get('apellido_materno', '')
        password = request.data.get('password')
        tipo = request.data.get('tipo')
        matricula = request.data.get('matricula')

        if not all([email, nombre, password, tipo, matricula]):
            return Response({"error": "Todos los campos obligatorios deben estar completos."}, status=400)

        if User.objects.filter(email=email).exists():
            return Response({"error": f"Email {email} ya registrado."}, status=400)

        if Alumnos.objects.filter(matricula=matricula).exists() or Administradores.objects.filter(matricula=matricula).exists():
            raise ValidationError({'matricula': 'Matrícula ya registrada.'})

        tipo_normalizado = tipo.lower()
        if tipo_normalizado != "alumno":
            return Response(
                {"error": "El registro público solo puede crear cuentas de Alumno."},
                status=403
            )

        user = User.objects.create_user(
            username=email, email=email,
            first_name=nombre,
            last_name=f"{apellido_paterno} {apellido_materno}".strip(),
            is_active=True
        )
        user.set_password(password)
        user.save()

        group, _ = Group.objects.get_or_create(name="alumno")
        group.user_set.add(user)

        alumno = Alumnos.objects.create(
            user=user, matricula=matricula, nombre=nombre,
            apellido_paterno=apellido_paterno, apellido_materno=apellido_materno
        )
        return Response({"id": alumno.id, "tipo": "Alumno"}, status=201)


# ─────────────────────────────────────────────────────────────
# Gestión de Administradores
# ─────────────────────────────────────────────────────────────

class AdminView(generics.CreateAPIView):
    """GET /admin/create/?id=X  |  POST /admin/create/ — Gestión de admins."""
    permission_classes = (AdminOnly,)

    def get(self, request, *args, **kwargs):
        admin_id = request.GET.get("id")
        if not admin_id:
            return Response({"error": "ID de administrador requerido."}, status=400)
        admin = get_object_or_404(Administradores, id=admin_id)
        return Response(AdminSerializer(admin).data)

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        validate_input(request.data)
        email = request.data.get('email')
        first_name = request.data.get('first_name')
        last_name = request.data.get('last_name', '')
        password = request.data.get('password')
        rol = request.data.get('rol')
        matricula = request.data.get('matricula')

        if not all([email, first_name, password, rol, matricula]):
            return Response({"error": "Todos los campos son obligatorios."}, status=400)

        if User.objects.filter(email=email).exists():
            return Response({"error": f"Email {email} ya registrado."}, status=400)

        user = User.objects.create_user(
            username=email, email=email,
            first_name=first_name, last_name=last_name, is_active=True
        )
        user.set_password(password)
        user.save()

        group, _ = Group.objects.get_or_create(name='administrador')
        group.user_set.add(user)

        admin = Administradores.objects.create(user=user, matricula=matricula)
        return Response({"admin_created_id": admin.id}, status=201)


# ─────────────────────────────────────────────────────────────
# Perfil del usuario autenticado
# ─────────────────────────────────────────────────────────────

class PerfilUsuarioView(APIView):
    """GET /perfil/  |  PUT /perfil/ — Perfil del usuario autenticado."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response(format_usuario_data(request.user))

    @transaction.atomic
    def put(self, request):
        validate_input(request.data, creating=False)
        user = request.user
        data = request.data

        alumno = Alumnos.objects.filter(user=user).first()
        admin = Administradores.objects.filter(user=user).first()

        if not alumno and not admin:
            return Response({"error": "No se encontró un perfil asociado."}, status=404)

        nombre = data.get('nombre')
        apellido_paterno = data.get('apellido_paterno')
        apellido_materno = data.get('apellido_materno')
        email = data.get('email')
        password = data.get('password')

        if email:
            if User.objects.filter(email__iexact=email).exclude(pk=user.pk).exists():
                raise ValidationError({'email': 'Correo ya registrado.'})
            user.email = email
            user.username = email

        if alumno:
            if nombre: alumno.nombre = nombre
            if apellido_paterno: alumno.apellido_paterno = apellido_paterno
            if apellido_materno is not None: alumno.apellido_materno = apellido_materno
            alumno.save()
        else:
            if nombre: user.first_name = nombre
            if apellido_paterno or apellido_materno is not None:
                user.last_name = f"{apellido_paterno or ''} {apellido_materno or ''}".strip()

        if password:
            user.set_password(password)
        user.save()

        return Response(basic_usuario_data(user))


# ─────────────────────────────────────────────────────────────
# ViewSet completo de usuarios (solo admins)
# ─────────────────────────────────────────────────────────────

class UsuariosViewSet(viewsets.ViewSet):
    """
    ViewSet completo para gestión de usuarios por parte de administradores.
    Endpoints: list, retrieve, create, update, desactivar, reactivar, ficha.
    """
    permission_classes = [permissions.IsAuthenticated]

    def list(self, request):
        if not _es_admin(request.user):
            return Response({"error": "Acceso restringido a Administradores."}, status=403)
        users = User.objects.all().order_by('id')
        return Response(enrich([basic_usuario_data(u) for u in users]))

    def retrieve(self, request, pk=None):
        if not _es_admin(request.user):
            return Response({"error": "Acceso restringido a Administradores."}, status=403)
        user = get_object_or_404(User, id=pk)
        return Response(format_usuario_data(user))

    @transaction.atomic
    def create(self, request):
        validate_input(request.data)
        if not _es_admin(request.user):
            return Response({"error": "Acceso restringido a Administradores."}, status=403)

        email = request.data.get('email')
        nombre = request.data.get('nombre')
        apellido_paterno = request.data.get('apellido_paterno', '')
        apellido_materno = request.data.get('apellido_materno', '')
        matricula = request.data.get('matricula')
        rol = request.data.get('rol', 'Estudiante')
        password = request.data.get('password')

        if not all([email, nombre, matricula, rol, password]):
            return Response({"error": "Faltan campos: email, nombre, matricula, rol."}, status=400)

        if User.objects.filter(email=email).exists():
            return Response({"error": f"El correo {email} ya está registrado."}, status=400)

        if Alumnos.objects.filter(matricula=matricula).exists() or \
           Administradores.objects.filter(matricula=matricula).exists():
            return Response({"error": f"La matrícula {matricula} ya está en uso."}, status=400)

        user = User.objects.create_user(
            username=email, email=email,
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
            Administradores.objects.create(user=user, matricula=matricula)
        else:
            group, _ = Group.objects.get_or_create(name='alumno')
            group.user_set.add(user)
            Alumnos.objects.create(
                user=user, matricula=matricula, nombre=nombre,
                apellido_paterno=apellido_paterno, apellido_materno=apellido_materno, rol=rol
            )

        return Response(basic_usuario_data(user), status=201)

    @transaction.atomic
    def update(self, request, pk=None):
        validate_input(request.data, creating=False)
        if not _es_admin(request.user):
            return Response({"error": "Acceso restringido a Administradores."}, status=403)

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
                return Response({"error": f"El correo {email} ya está registrado."}, status=400)
            user.email = email
            user.username = email

        if nombre: user.first_name = nombre
        if apellido_paterno or apellido_materno:
            user.last_name = f"{apellido_paterno} {apellido_materno}".strip()
        if password: user.set_password(password)
        user.save()

        alumno = Alumnos.objects.filter(user=user).first()
        admin = Administradores.objects.filter(user=user).first()
        if rol and ((alumno and rol.lower() in ('admin','administrador','bibliotecario')) or
                    (admin and rol.lower() not in ('admin','administrador','bibliotecario'))):
            raise ValidationError({'rol':'El cambio de tipo de cuenta requiere migrar su perfil explícitamente.'})
        if alumno:
            if nombre: alumno.nombre = nombre
            if apellido_paterno: alumno.apellido_paterno = apellido_paterno
            if apellido_materno is not None: alumno.apellido_materno = apellido_materno
            if matricula: alumno.matricula = matricula
            if rol: alumno.rol = rol
            alumno.save()
        elif admin:
            if matricula: admin.matricula = matricula
            admin.save()

        return Response(basic_usuario_data(user))

    @action(detail=True, methods=['post'], url_path='desactivar')
    def desactivar(self, request, pk=None):
        if not _es_admin(request.user):
            return Response({"error": "Acceso restringido a Administradores."}, status=403)
        user = get_object_or_404(User, id=pk)
        user.is_active = False
        user.save()
        return Response({"message": f"Usuario '{user.email}' desactivado.", "usuario": basic_usuario_data(user)})

    @action(detail=True, methods=['post'], url_path='reactivar')
    def reactivar(self, request, pk=None):
        if not _es_admin(request.user):
            return Response({"error": "Acceso restringido a Administradores."}, status=403)
        user = get_object_or_404(User, id=pk)
        user.is_active = True
        user.save()
        return Response({"message": f"Usuario '{user.email}' reactivado.", "usuario": basic_usuario_data(user)})

    @action(detail=True, methods=['get'], url_path='ficha')
    def ficha(self, request, pk=None):
        if not _es_admin(request.user):
            return Response({"error": "Acceso restringido a Administradores."}, status=403)
        user = get_object_or_404(User, id=pk)
        data = format_usuario_data(user)
        return Response(data)

    @action(detail=True, methods=['post'], url_path='pagar-multa')
    def pagar_multa(self, request, pk=None):
        if not _es_admin(request.user):
            return Response({'detail': 'Acceso restringido.'}, status=403)
        user = get_object_or_404(User, pk=pk)
        alumno = get_object_or_404(Alumnos, user=user)
        result = call(settings.LOANS_URL, '/internal/pagar-multa/', {
            'alumno_id': alumno.pk, 'prestamo_id': request.data.get('prestamo_id')})
        result['usuario'] = format_usuario_data(user)
        return Response(result)
