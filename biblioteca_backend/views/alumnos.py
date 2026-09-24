from django.shortcuts import get_object_or_404
from django.db import transaction
from rest_framework import generics, permissions
from rest_framework.response import Response
from django.contrib.auth.models import Group
from django.contrib.auth import get_user_model
from biblioteca_backend.models import Alumnos, Administradores
from biblioteca_backend.serializers import AlumnoSerializer

User = get_user_model()


class AlumnosAll(generics.ListAPIView):
    """
    Listado de todos los alumnos activos.
    """
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = AlumnoSerializer

    def get_queryset(self):
        return Alumnos.objects.filter(user__is_active=True).order_by("id")


class AlumnosView(generics.CreateAPIView):
    """
    Registro de alumnos (y administradores si es necesario).
    """
    permission_classes = (permissions.AllowAny,)
    serializer_class = AlumnoSerializer

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        print("Datos recibidos en POST:", request.data)

        email = request.data.get('email')
        nombre = request.data.get('nombre', '')
        apellido_paterno = request.data.get('apellido_paterno', '')
        apellido_materno = request.data.get('apellido_materno', '')
        password = request.data.get('password')
        tipo = request.data.get('tipo')
        matricula = request.data.get('matricula')

        # Verificar campos obligatorios
        missing_fields = [k for k, v in {
            "email": email,
            "password": password,
            "tipo": tipo,
            "matricula": matricula
        }.items() if not v]

        if missing_fields:
            return Response(
                {"error": f"Faltan campos obligatorios: {', '.join(missing_fields)}"},
                status=400
            )

        tipo_normalizado = tipo.lower()
        if tipo_normalizado not in ["alumno", "administrador"]:
            return Response(
                {"error": f"Tipo de usuario inválido: {tipo}"},
                status=400
            )

        # Crear usuario
        user = User.objects.create_user(
            username=email,
            email=email,
            first_name=nombre,
            last_name=f"{apellido_paterno} {apellido_materno}".strip()
        )
        user.set_password(password)
        user.save()

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
