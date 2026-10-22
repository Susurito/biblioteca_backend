# biblioteca_backend/views/auth.py

from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.authtoken.models import Token
from rest_framework import status, generics, permissions
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from biblioteca_backend.models import Alumnos, Administradores
from biblioteca_backend.serializers import AlumnoSerializer, UserSerializer



User = get_user_model()


class CustomAuthToken(ObtainAuthToken):
    """
    Login y retorno de token, junto con rol del usuario.
    Permite autenticarse flexiblemente con correo electrónico, username,
    prefijo (ej. 'admi' para 'admi@gmail.com') o matrícula.
    """
    def post(self, request, *args, **kwargs):
        username_or_email = (request.data.get('username') or request.data.get('email') or '').strip()
        password = (request.data.get('password') or '').strip()

        if not username_or_email or not password:
            return Response(
                {"error": "Por favor ingresa usuario/correo y contraseña."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 1. Buscar usuario flexiblemente: por username, email o prefijo
        user = (
            User.objects.filter(username__iexact=username_or_email).first() or
            User.objects.filter(email__iexact=username_or_email).first() or
            User.objects.filter(email__istartswith=username_or_email + '@').first() or
            User.objects.filter(username__istartswith=username_or_email + '@').first()
        )

        # 2. Si no se encuentra, buscar por matrícula de Administrador o Alumno
        if not user:
            admin_obj = Administradores.objects.filter(matricula=username_or_email).first()
            if admin_obj:
                user = admin_obj.user
            else:
                alu_obj = Alumnos.objects.filter(matricula=username_or_email).first()
                if alu_obj:
                    user = alu_obj.user

        # 3. Validar contraseña
        authenticated_user = None
        if user and user.check_password(password):
            authenticated_user = user
        # authenticated_user = None
        # if user:
        #     if user.check_password(password):
        #         authenticated_user = user
        #     else:
        #         # Contraseñas comunes de desarrollo para permitir acceso inmediato si se restableció
        #         passwords_admin_comunes = [
        #             'admi', 'admin', '1234', '12345', '123456', '12345678',
        #             'admi123', 'admin123', 'Admin123', 'Admin123!', 'Admin1234', 'Admin1234!',
        #             '202248698', 'password'
        #         ]
        #         es_admin = (
        #             user.groups.filter(name__iexact='administrador').exists() or
        #             user.is_superuser or
        #             Administradores.objects.filter(user=user).exists()
        #         )
        #         if es_admin and password in passwords_admin_comunes:
        #             user.set_password(password)
        #             user.save()
        #             authenticated_user = user
        #         elif user.groups.filter(name__iexact='alumno').exists() and password in ['1234', '123456', '12345678', 'alumno', 'Alumno1234!', '202248699']:
        #             user.set_password(password)
        #             user.save()
        #             authenticated_user = user

        # 4. Fallback con autenticación nativa
        if not authenticated_user:
            from django.contrib.auth import authenticate
            authenticated_user = authenticate(request=request, username=username_or_email, password=password)

        if not authenticated_user:
            return Response(
                {"error": "Credenciales incorrectas. Verifica tu correo y contraseña."},
                status=status.HTTP_400_BAD_REQUEST
            )

        user = authenticated_user
        if not user.is_active:
            return Response({"error": "Usuario inactivo."}, status=status.HTTP_403_FORBIDDEN)

        # 5. Determinar rol
        roles = user.groups.all()
        if user.is_superuser or user.groups.filter(name__iexact='administrador').exists() or Administradores.objects.filter(user=user).exists():
            role_name = "administrador"
        elif user.groups.filter(name__iexact='alumno').exists() or Alumnos.objects.filter(user=user).exists():
            role_name = "alumno"
        elif roles.exists():
            role_name = roles[0].name.lower()
        else:
            return Response({"details": "Usuario sin rol asignado"}, status=403)

        # 6. Crear o recuperar token
        token, created = Token.objects.get_or_create(user=user)

        if role_name == "alumno":
            alumno = Alumnos.objects.filter(user=user).first()
            data = AlumnoSerializer(alumno).data if alumno else {}
            data["token"] = token.key
            data["rol"] = "alumno"
            data["nombre"] = user.first_name or user.username
            return Response(data, status=status.HTTP_200_OK)

        elif role_name == "administrador":
            data = UserSerializer(user, many=False).data
            data["token"] = token.key
            data["rol"] = "administrador"
            data["nombre"] = user.first_name or "Administrador"
            return Response(data, status=status.HTTP_200_OK)

        else:
            return Response({"details": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)


class Logout(generics.GenericAPIView):
    """
    Cierre de sesión: borra el token del usuario.
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
                return Response({'logout': False, 'detail': 'Token no existe'})
        return Response({'logout': False})