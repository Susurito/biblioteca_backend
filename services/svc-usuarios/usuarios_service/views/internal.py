"""
Endpoints INTERNOS de svc-usuarios.

Estos endpoints NO están expuestos públicamente a través del API Gateway.
Son solo para comunicación inter-servicios (svc-auth, svc-prestamos, etc.).

Rutas:
  GET /internal/resolver-usuario/?q=<username|email|matricula>
      → Retorna { user_id, rol, nombre } para que svc-auth resuelva el login

  GET /internal/alumnos/<id>/
      → Retorna datos de un alumno por id (para svc-prestamos en Fase 4)

  GET /internal/alumnos/<matricula>/por-matricula/
      → Retorna datos de un alumno por matrícula
"""

from django.contrib.auth import get_user_model
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from usuarios_service.models import Administradores, Alumnos

User = get_user_model()

# Permiso de acceso solo desde la red interna de Docker.
# En producción real, se agregaría validación de IP o token de servicio.
# Por ahora usamos AllowAny ya que nginx NO expone /internal/ al exterior.
_INTERNAL_PERMISSION = [permissions.AllowAny]


class ResolverUsuarioView(APIView):
    """
    GET /internal/resolver-usuario/?q=<query>

    Busca un usuario por username, email, o matrícula (alumno o admin).
    Usado por svc-auth para resolver el login cuando el monolito ya no existe.

    Respuesta 200:
      { user_id, username, email, nombre, rol, grupos }

    Respuesta 404:
      { detail: "Usuario no encontrado." }
    """
    permission_classes = _INTERNAL_PERMISSION

    def get(self, request):
        q = (request.query_params.get('q') or '').strip()
        if not q:
            return Response({"detail": "Parámetro 'q' requerido."}, status=400)

        user = (
            User.objects.filter(username__iexact=q).first() or
            User.objects.filter(email__iexact=q).first() or
            User.objects.filter(email__istartswith=q + '@').first()
        )

        # Buscar por matrícula si no se encontró por username/email
        if not user:
            admin_obj = Administradores.objects.filter(matricula=q).first()
            if admin_obj:
                user = admin_obj.user
            else:
                alu_obj = Alumnos.objects.filter(matricula=q).first()
                if alu_obj:
                    user = alu_obj.user

        if not user:
            return Response({"detail": "Usuario no encontrado."}, status=404)

        # Determinar rol
        if user.is_superuser or user.groups.filter(name__iexact='administrador').exists() or \
           Administradores.objects.filter(user=user).exists():
            rol = "administrador"
        elif user.groups.filter(name__iexact='alumno').exists() or \
             Alumnos.objects.filter(user=user).exists():
            rol = "alumno"
        else:
            grupos = list(user.groups.values_list('name', flat=True))
            rol = grupos[0] if grupos else "sin_rol"

        return Response({
            "user_id": user.id,
            "username": user.username,
            "email": user.email,
            "nombre": user.first_name or user.username,
            "rol": rol,
            "grupos": list(user.groups.values_list('name', flat=True)),
            "is_active": user.is_active,
        })


class AlumnoInternalView(APIView):
    """
    GET /internal/alumnos/<pk>/
    Retorna datos básicos de un alumno por su ID de modelo.
    Usado por svc-prestamos en Fase 4 para validar el alumno antes de un préstamo.
    """
    permission_classes = _INTERNAL_PERMISSION

    def get(self, request, pk):
        try:
            alumno = Alumnos.objects.get(pk=pk)
        except Alumnos.DoesNotExist:
            return Response({"detail": "Alumno no encontrado."}, status=404)

        return Response({
            "id": alumno.id,
            "user_id": alumno.user.id,
            "matricula": alumno.matricula,
            "nombre": alumno.nombre,
            "apellido_paterno": alumno.apellido_paterno,
            "apellido_materno": alumno.apellido_materno,
            "email": alumno.user.email,
            "is_active": alumno.user.is_active,
            "rol": alumno.rol,
        })


class AlumnoPorMatriculaView(APIView):
    """
    GET /internal/alumnos/<matricula>/por-matricula/
    Retorna datos básicos de un alumno por su matrícula.
    """
    permission_classes = _INTERNAL_PERMISSION

    def get(self, request, matricula):
        try:
            alumno = Alumnos.objects.get(matricula=matricula)
        except Alumnos.DoesNotExist:
            return Response({"detail": f"Alumno con matrícula {matricula} no encontrado."}, status=404)

        return Response({
            "id": alumno.id,
            "user_id": alumno.user.id,
            "matricula": alumno.matricula,
            "nombre": alumno.nombre,
            "apellido_paterno": alumno.apellido_paterno,
            "apellido_materno": alumno.apellido_materno,
            "email": alumno.user.email,
            "is_active": alumno.user.is_active,
            "rol": alumno.rol,
        })
