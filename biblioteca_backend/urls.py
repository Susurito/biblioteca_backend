from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from biblioteca_backend.views import bootstrap
from biblioteca_backend.views.users import UsuariosView, AdminView, UsuariosViewSet
from biblioteca_backend.views.alumnos import AlumnosView, AlumnosAll
from biblioteca_backend.views.auth import CustomAuthToken, Logout
from biblioteca_backend.views.users import PerfilUsuarioView
from biblioteca_backend.views.views import LibrosViewSet, PrestamosViewSet, SolicitarPrestamoView

# Crear router para el ViewSet de libros
router = DefaultRouter()
router.register(r'libros', LibrosViewSet, basename='libros')
router.register(r'prestamos', PrestamosViewSet, basename='prestamos')
router.register(r'usuarios', UsuariosViewSet, basename='usuarios')

urlpatterns = [
    # Version
    path('bootstrap/version', bootstrap.VersionView.as_view()),

    # Admin
    path('admin/create/', AdminView.as_view()),

    # Alumnos
    path('alumnos/', AlumnosView.as_view()),
    path('alumnos/all/', AlumnosAll.as_view()),

    # Registro de usuarios
    path('register/', UsuariosView.as_view(), name='register'),

    # Token custom
    path('custom-token/', CustomAuthToken.as_view(), name='custom_token'),
    path('token/', CustomAuthToken.as_view(), name='token_obtain_pair'),

    # Logout
    path('logout/', Logout.as_view()),

    path('perfil/', PerfilUsuarioView.as_view(), name='perfil_usuario'),

    # CAMBIO IMPORTANTE: Incluir router URLs ANTES de las rutas manuales
    path('', include(router.urls)),
    
    # CAMBIO: Usar una ruta diferente para evitar conflicto
    path('solicitar-prestamo/', SolicitarPrestamoView.as_view(), name='solicitar-prestamo'),
]