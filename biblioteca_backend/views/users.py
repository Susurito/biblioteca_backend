from django.shortcuts import get_object_or_404
from django.db import transaction
from rest_framework import generics, permissions, status
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
        if tipo_normalizado not in ["alumno", "administrador"]:
            user.delete()
            return Response({"error": "Tipo de usuario no válido"}, status=400)

        # Crear o asignar grupo
        group, _ = Group.objects.get_or_create(name=tipo_normalizado)
        group.user_set.add(user)

        # Crear registro según tipo
        if tipo_normalizado == "alumno":
            alumno = Alumnos.objects.create(
                user=user,
                matricula=matricula,
                nombre=nombre,
                apellido_paterno=apellido_paterno,
                apellido_materno=apellido_materno
            )
            return Response({"id": alumno.id, "tipo": "Alumno"}, status=201)

        elif tipo_normalizado == "administrador":
            admin = Administradores.objects.create(
                user=user,
                matricula=matricula
            )
            return Response({"id": admin.id, "tipo": "Administrador"}, status=201)


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
            perfil = {
                "nombre": alumno.nombre,
                "apellido_paterno": alumno.apellido_paterno,
                "apellido_materno": alumno.apellido_materno,
                "email": user.email,
                "matricula": alumno.matricula,
                "rol": "Alumno"
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