from django.db import transaction
from rest_framework import generics, permissions
from rest_framework.response import Response
from django.contrib.auth.models import Group
from django.contrib.auth import get_user_model
from biblioteca_backend.models import Alumnos
from biblioteca_backend.serializers import AlumnoSerializer

from biblioteca_backend.permissions import AdminOnly

User = get_user_model()


class AlumnosAll(generics.ListAPIView):
    """
    Listado de todos los alumnos activos.
    """
    permission_classes = (AdminOnly,)
    serializer_class = AlumnoSerializer

    def get_queryset(self):
        return Alumnos.objects.filter(user__is_active=True).order_by("id")


class AlumnosView(generics.CreateAPIView):
    """
    Registro público de alumnos.
    Solo permite crear cuentas de tipo Alumno; los Administradores
    deben ser dados de alta por otro administrador autenticado.
    """
    permission_classes = (permissions.AllowAny,)
    serializer_class = AlumnoSerializer

    @transaction.atomic
    def post(self, request, *args, **kwargs):
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
        if tipo_normalizado != "alumno":
            return Response(
                {"error": "El registro público solo puede crear cuentas de Alumno. "
                          "Las cuentas de Administrador deben darlas de alta otro administrador autenticado."},
                status=403
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

        # Asignar grupo alumno
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
