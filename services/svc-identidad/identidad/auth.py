from django.contrib.auth import get_user_model
from django.db.models import Q
from rest_framework.authtoken.models import Token
from rest_framework.authentication import TokenAuthentication
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from biblioteca_common.auth import InternalOnly
from .models import Alumnos, Administradores
from .users import basic_usuario_data

User = get_user_model()

class Login(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        query = str(request.data.get('username') or request.data.get('email') or '').strip()
        password = request.data.get('password') or ''
        if not query or not password:
            return Response({'error': 'Usuario y contraseña requeridos.'}, status=400)
        qs = User.objects.filter(Q(username__iexact=query) | Q(email__iexact=query) |
                                 Q(alumnos__matricula=query) | Q(administradores__matricula=query)).distinct()
        user = qs.first() if qs.count() == 1 else None
        if not user or not user.check_password(password):
            return Response({'error': 'Credenciales incorrectas.'}, status=400)
        if not user.is_active:
            return Response({'error': 'Usuario inactivo.'}, status=403)
        token, _ = Token.objects.get_or_create(user=user)
        data = basic_usuario_data(user)
        return Response(dict(token=token.key, **data))

class Logout(APIView):
    def post(self, request):
        Token.objects.filter(user=request.user).delete()
        return Response({'logout': True})
    def get(self, request):
        return self.post(request)

class Validate(APIView):
    permission_classes = [InternalOnly, IsAuthenticated]
    authentication_classes = [TokenAuthentication]
    def get(self, request):
        data = basic_usuario_data(request.user)
        return Response(dict(valid=True, is_superuser=request.user.is_superuser, **data))

class InternalAlumnos(APIView):
    authentication_classes = []
    permission_classes = [InternalOnly]
    def post(self, request):
        ids = request.data.get('alumno_ids', [])
        if not isinstance(ids, list) or len(ids) > 1000:
            return Response({'detail': 'Máximo 1000 identificadores.'}, status=400)
        return Response({str(a.id): basic_usuario_data(a.user) for a in
                         Alumnos.objects.filter(id__in=ids).select_related('user')})

class InternalUsers(APIView):
    authentication_classes = []
    permission_classes = [InternalOnly]
    def get(self, request, pk):
        from django.shortcuts import get_object_or_404
        return Response(basic_usuario_data(get_object_or_404(User, pk=pk)))
