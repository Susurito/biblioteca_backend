# biblioteca_backend/views/auth.py

from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.authtoken.models import Token
from rest_framework import status, generics, permissions
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from biblioteca_backend.models import Alumnos
from biblioteca_backend.serializers import AlumnoSerializer, UserSerializer



User = get_user_model()


class CustomAuthToken(ObtainAuthToken):
    """
    Login y retorno de token, junto con rol del usuario.
    """
    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(
            data=request.data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']

        if not user.is_active:
            return Response({}, status=status.HTTP_403_FORBIDDEN)

        # Obtener rol del usuario
        roles = user.groups.all()
        if not roles.exists():
            return Response({"details": "Usuario sin rol asignado"}, status=403)

        role_name = roles[0].name.lower()  # Tomamos el primer rol

        # Crear token
        token, created = Token.objects.get_or_create(user=user)

        if role_name == "alumno":
            alumno = Alumnos.objects.filter(user=user).first()
            data = AlumnoSerializer(alumno).data
            data["token"] = token.key
            data["rol"] = "alumno"
            return Response(data, status=200)

        elif role_name == "administrador":
            data = UserSerializer(user, many=False).data
            data["token"] = token.key
            data["rol"] = "administrador"
            return Response(data, status=200)

        else:
            return Response({"details": "Forbidden"}, status=403)


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