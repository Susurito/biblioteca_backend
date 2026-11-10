from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from identidad.auth import Login, Logout, Validate, InternalAlumnos, InternalUsers
from identidad.users import UsuariosView, AdminView, PerfilUsuarioView, UsuariosViewSet
from identidad.alumnos import AlumnosView, AlumnosAll
router = DefaultRouter()
router.register('usuarios', UsuariosViewSet, basename='usuarios')
@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
def health(request):
    return Response({'status': 'ok'})
urlpatterns = [
    path('health/', health), path('token/', Login.as_view()), path('custom-token/', Login.as_view()),
    path('logout/', Logout.as_view()), path('internal/validate/', Validate.as_view()),
    path('validate/', Validate.as_view()), path('internal/alumnos/', InternalAlumnos.as_view()),
    path('internal/usuarios/<int:pk>/', InternalUsers.as_view()),
    path('register/', UsuariosView.as_view()), path('admin/create/', AdminView.as_view()),
    path('alumnos/', AlumnosView.as_view()), path('alumnos/all/', AlumnosAll.as_view()),
    path('perfil/', PerfilUsuarioView.as_view()), path('', include(router.urls)),
]
