"""
Vistas de gestión de usuarios para svc-usuarios.
Adaptación de biblioteca_backend/views/users.py.

Nota: La función format_usuario_data en el monolito consultaba Prestamos
para calcular bloqueos. En svc-usuarios (Fase 2), ese dato vendrá de
svc-prestamos via HTTP cuando esté disponible (Fase 4). Por ahora
retorna bloqueado=False como placeholder.
"""

from django.db import transaction
from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from rest_framework import generics, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from usuarios_service.models import Administradores, Alumnos
from usuarios_service.serializers import AdminSerializer, AlumnoSerializer, UserSerializer

User = get_user_model()


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


def format_usuario_data(user) -> dict:
    """
    Construye el dict de datos completos de un usuario.
    El estado de bloqueo (bloqueado/multas) se consultará a svc-prestamos
    en Fase 4. Por ahora retorna valores neutros.
    """
    alumno = Alumnos.objects.filter(user=user).first()
    admin = Administradores.objects.filter(user=user).first()

    if alumno:
        nombre = alumno.nombre
        apellido_paterno = alumno.apellido_paterno
        apellido_materno = alumno.apellido_materno
        matricula = alumno.matricula
        rol = alumno.rol or 'Estudiante'
        tipo_modelo = 'alumno'
        modelo_id = alumno.id
    elif admin:
        nombre = user.first_name
        apellido_paterno = user.last_name
        apellido_materno = ''
        matricula = admin.matricula
        rol = 'Bibliotecario'
        tipo_modelo = 'admin'
        modelo_id = admin.id
    else:
        nombre = user.first_name
        apellido_paterno = user.last_name
        apellido_materno = ''
        matricula = user.username
        rol = 'Estudiante'
        tipo_modelo = 'user'
        modelo_id = user.id

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
        "nombre_completo": f"{nombre} {apellido_paterno} {apellido_materno}".strip(),
        "matricula": matricula,
        "rol": rol,
        "is_active": user.is_active,
        # Placeholder: se enriquecerá con datos de svc-prestamos en Fase 4
        "bloqueado": False,
        "bloqueo_motivo": "",
        "bloqueo_hasta": None,
        "prestamos_activos": 0,
        "limite_prestamos": 3,
        "estado": "Activo" if user.is_active else "Inactivo",
    }


# ─────────────────────────────────────────────────────────────
# Registro público
# ─────────────────────────────────────────────────────────────

class UsuariosView(generics.CreateAPIView):
    """POST /register/ — Registro público (solo alumnos)."""
    permission_classes = (permissions.AllowAny,)

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
            return Response({"error": "Todos los campos obligatorios deben estar completos."}, status=400)

        if User.objects.filter(email=email).exists():
            return Response({"error": f"Email {email} ya registrado."}, status=400)

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
    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request, *args, **kwargs):
        admin_id = request.GET.get("id")
        if not admin_id:
            return Response({"error": "ID de administrador requerido."}, status=400)
        admin = get_object_or_404(Administradores, id=admin_id)
        return Response(AdminSerializer(admin).data)

    @transaction.atomic
    def post(self, request, *args, **kwargs):
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

        group, _ = Group.objects.get_or_create(name=rol.lower())
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
            user.email = email

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

        return Response(format_usuario_data(user))


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
        return Response([format_usuario_data(u) for u in users])

    def retrieve(self, request, pk=None):
        if not _es_admin(request.user):
            return Response({"error": "Acceso restringido a Administradores."}, status=403)
        user = get_object_or_404(User, id=pk)
        return Response(format_usuario_data(user))

    @transaction.atomic
    def create(self, request):
        if not _es_admin(request.user):
            return Response({"error": "Acceso restringido a Administradores."}, status=403)

        email = request.data.get('email')
        nombre = request.data.get('nombre')
        apellido_paterno = request.data.get('apellido_paterno', '')
        apellido_materno = request.data.get('apellido_materno', '')
        matricula = request.data.get('matricula')
        rol = request.data.get('rol', 'Estudiante')
        password = request.data.get('password', '123456')

        if not all([email, nombre, matricula, rol]):
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

        return Response(format_usuario_data(user), status=201)

    @transaction.atomic
    def update(self, request, pk=None):
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

        return Response(format_usuario_data(user))

    @action(detail=True, methods=['post'], url_path='desactivar')
    def desactivar(self, request, pk=None):
        if not _es_admin(request.user):
            return Response({"error": "Acceso restringido a Administradores."}, status=403)
        user = get_object_or_404(User, id=pk)
        user.is_active = False
        user.save()
        return Response({"message": f"Usuario '{user.email}' desactivado.", "usuario": format_usuario_data(user)})

    @action(detail=True, methods=['post'], url_path='reactivar')
    def reactivar(self, request, pk=None):
        if not _es_admin(request.user):
            return Response({"error": "Acceso restringido a Administradores."}, status=403)
        user = get_object_or_404(User, id=pk)
        user.is_active = True
        user.save()
        return Response({"message": f"Usuario '{user.email}' reactivado.", "usuario": format_usuario_data(user)})

    @action(detail=True, methods=['get'], url_path='ficha')
    def ficha(self, request, pk=None):
        if not _es_admin(request.user):
            return Response({"error": "Acceso restringido a Administradores."}, status=403)
        user = get_object_or_404(User, id=pk)
        data = format_usuario_data(user)
        # historial_prestamos se enriquecerá desde svc-prestamos en Fase 4
        data['historial_prestamos'] = []
        return Response(data)
