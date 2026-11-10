"""
Vistas de autenticación para svc-auth.

Esta es la versión adaptada de biblioteca_backend/views/auth.py
para operar como microservicio independiente.

Diferencia clave respecto al monolito:
  - Ya no importa los modelos Alumnos/Administradores directamente.
  - Consulta svc-usuarios via HTTP para resolver el usuario y su rol.
  - Si svc-usuarios no está disponible, hace fallback a auth.User local.
"""

import requests
from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from rest_framework import generics, permissions, status
from rest_framework.authtoken.models import Token
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.response import Response

User = get_user_model()


def _resolve_user_from_usuarios_service(username_or_email: str) -> dict | None:
    """
    Consulta svc-usuarios para encontrar un usuario por username/email/matrícula.
    Retorna un dict con {user_id, rol, nombre} o None si no se encuentra.
    Esto permite que svc-auth NO tenga modelos de Alumnos/Administradores.
    """
    base_url = getattr(settings, 'USUARIOS_SERVICE_URL', None)
    if not base_url:
        return None

    try:
        # Endpoint interno de svc-usuarios (se implementa en Fase 2)
        resp = requests.get(
            f"{base_url}/internal/resolver-usuario/",
            params={"q": username_or_email},
            timeout=3,
        )
        if resp.status_code == 200:
            return resp.json()
    except requests.RequestException:
        # Si svc-usuarios no está disponible, continúa con fallback local
        pass
    return None


class CustomAuthToken(ObtainAuthToken):
    """
    Login: retorna token + datos del usuario con su rol.

    Estrategia de resolución de usuario (en orden):
      1. Buscar en auth.User local por username o email
      2. Consultar svc-usuarios para resolver por matrícula o prefijo de email
      3. Fallback con authenticate() nativo de Django
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        username_or_email = (
            request.data.get('username') or
            request.data.get('email') or ''
        ).strip()
        password = (request.data.get('password') or '').strip()

        if not username_or_email or not password:
            return Response(
                {"error": "Por favor ingresa usuario/correo y contraseña."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # ── Paso 1: Buscar en auth.User local (username o email) ──────────
        user = (
            User.objects.filter(username__iexact=username_or_email).first() or
            User.objects.filter(email__iexact=username_or_email).first() or
            User.objects.filter(email__istartswith=username_or_email + '@').first()
        )

        # ── Paso 2: Consultar svc-usuarios si no se encontró localmente ───
        if not user:
            svc_data = _resolve_user_from_usuarios_service(username_or_email)
            if svc_data and 'user_id' in svc_data:
                user = User.objects.filter(id=svc_data['user_id']).first()

        # ── Paso 3: Validar contraseña ─────────────────────────────────────
        authenticated_user = None
        if user and user.check_password(password):
            authenticated_user = user

        # ── Paso 4: Fallback con authenticate() nativo de Django ───────────
        if not authenticated_user:
            authenticated_user = authenticate(
                request=request,
                username=username_or_email,
                password=password
            )

        if not authenticated_user:
            return Response(
                {"error": "Credenciales incorrectas. Verifica tu correo y contraseña."},
                status=status.HTTP_400_BAD_REQUEST
            )

        user = authenticated_user
        if not user.is_active:
            return Response(
                {"error": "Usuario inactivo."},
                status=status.HTTP_403_FORBIDDEN
            )

        # ── Paso 5: Determinar rol ─────────────────────────────────────────
        if user.is_superuser or user.groups.filter(name__iexact='administrador').exists():
            role_name = "administrador"
        elif user.groups.filter(name__iexact='alumno').exists():
            role_name = "alumno"
        else:
            grupos = user.groups.all()
            if grupos.exists():
                role_name = grupos[0].name.lower()
            else:
                return Response(
                    {"detail": "Usuario sin rol asignado."},
                    status=status.HTTP_403_FORBIDDEN
                )

        # ── Paso 6: Crear o recuperar token ───────────────────────────────
        token, _ = Token.objects.get_or_create(user=user)

        return Response({
            "token": token.key,
            "user_id": user.id,
            "username": user.username,
            "email": user.email,
            "nombre": user.first_name or user.username,
            "rol": role_name,
        }, status=status.HTTP_200_OK)


class Logout(generics.GenericAPIView):
    """
    Cierre de sesión: invalida el token del usuario autenticado.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        user = request.user
        if user.is_active:
            try:
                token = Token.objects.get(user=user)
                token.delete()
                return Response({'logout': True})
            except Token.DoesNotExist:
                return Response({'logout': False, 'detail': 'Token no existe.'})
        return Response({'logout': False})


class ValidateToken(generics.GenericAPIView):
    """
    Endpoint NUEVO: permite a otros microservicios verificar si un token
    es válido sin implementar lógica de auth propia.

    GET /validate/
    Header: Authorization: Token <token>

    Responde:
      200 { valid: true, user_id, username, rol }
      401 { valid: false }
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        user = request.user
        grupos = list(user.groups.values_list('name', flat=True))
        return Response({
            "valid": True,
            "user_id": user.id,
            "username": user.username,
            "email": user.email,
            "nombre": user.first_name or user.username,
            "es_superuser": user.is_superuser,
            "grupos": grupos,
        })
