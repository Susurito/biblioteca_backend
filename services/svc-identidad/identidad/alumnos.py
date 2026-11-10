"""Dominio de identidad: cuentas, roles, alumnos y administradores."""

from django.db import transaction
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from rest_framework import generics, permissions
from rest_framework.response import Response

from identidad.models import Alumnos
from identidad.serializers import AlumnoSerializer
from .users import AdminOnly, validate_input

User = get_user_model()


class AlumnosAll(generics.ListAPIView):
    """
    GET /alumnos/all/ — Listado de todos los alumnos activos.
    Solo accesible por administradores autenticados.
    """
    permission_classes = (AdminOnly,)
    serializer_class = AlumnoSerializer

    def get_queryset(self):
        return Alumnos.objects.filter(user__is_active=True).order_by("id")


class AlumnosView(generics.CreateAPIView):
    """
    POST /alumnos/ — Registro público de alumnos.
    Solo permite crear cuentas de tipo Alumno.
    """
    permission_classes = (permissions.AllowAny,)
    serializer_class = AlumnoSerializer

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        validate_input(request.data)
        email = request.data.get('email')
        nombre = request.data.get('nombre', '')
        apellido_paterno = request.data.get('apellido_paterno', '')
        apellido_materno = request.data.get('apellido_materno', '')
        password = request.data.get('password')
        tipo = request.data.get('tipo')
        matricula = request.data.get('matricula')

        missing_fields = [k for k, v in {
            "email": email, "password": password,
            "tipo": tipo, "matricula": matricula
        }.items() if not v]

        if missing_fields:
            return Response(
                {"error": f"Faltan campos obligatorios: {', '.join(missing_fields)}"},
                status=400
            )

        tipo_normalizado = tipo.lower()
        if tipo_normalizado != "alumno":
            return Response(
                {"error": "El registro público solo puede crear cuentas de Alumno."},
                status=403
            )

        if User.objects.filter(email=email).exists():
            return Response({"error": f"Email {email} ya registrado."}, status=400)

        if Alumnos.objects.filter(matricula=matricula).exists():
            return Response({"error": f"Matrícula {matricula} ya en uso."}, status=400)

        user = User.objects.create_user(
            username=email,
            email=email,
            first_name=nombre,
            last_name=f"{apellido_paterno} {apellido_materno}".strip(),
            is_active=True
        )
        user.set_password(password)
        user.save()

        group, _ = Group.objects.get_or_create(name="alumno")
        group.user_set.add(user)

        alumno = Alumnos.objects.create(
            user=user,
            matricula=matricula,
            nombre=nombre,
            apellido_paterno=apellido_paterno,
            apellido_materno=apellido_materno
        )
        return Response({"id": alumno.id, "tipo": "Alumno"}, status=201)
