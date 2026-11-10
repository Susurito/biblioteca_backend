"""
URLs de svc-usuarios.

Rutas públicas (expuestas a través del API Gateway en nginx):
  POST /register/          → Registro de alumnos
  POST /admin/create/      → Crear administrador (requiere auth)
  GET  /admin/create/      → Obtener admin por ID
  GET  /alumnos/           → Listado de alumnos (público para registro)
  GET  /alumnos/all/       → Todos los alumnos activos
  GET  /perfil/            → Perfil del usuario autenticado
  PUT  /perfil/            → Actualizar perfil
  GET/POST/PUT /usuarios/  → ViewSet completo de usuarios

Rutas internas (solo acceso Docker interno, no pasan por nginx público):
  GET  /internal/resolver-usuario/?q=<query>
  GET  /internal/alumnos/<pk>/
  GET  /internal/alumnos/<matricula>/por-matricula/
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from usuarios_service.views.users import (
    UsuariosView, AdminView, PerfilUsuarioView, UsuariosViewSet
)
from usuarios_service.views.alumnos import AlumnosView, AlumnosAll
from usuarios_service.views.internal import (
    ResolverUsuarioView, AlumnoInternalView, AlumnoPorMatriculaView
)

router = DefaultRouter()
router.register(r'usuarios', UsuariosViewSet, basename='usuarios')

urlpatterns = [
    # ── Rutas públicas ─────────────────────────────────────
    path('register/', UsuariosView.as_view(), name='register'),
    path('admin/create/', AdminView.as_view(), name='admin_create'),
    path('alumnos/', AlumnosView.as_view(), name='alumnos_create'),
    path('alumnos/all/', AlumnosAll.as_view(), name='alumnos_all'),
    path('perfil/', PerfilUsuarioView.as_view(), name='perfil'),

    # ViewSet (list, retrieve, create, update, desactivar, reactivar, ficha)
    path('', include(router.urls)),

    # ── Rutas internas (solo inter-servicios) ───────────────
    path('internal/resolver-usuario/', ResolverUsuarioView.as_view(), name='internal_resolver'),
    path('internal/alumnos/<int:pk>/', AlumnoInternalView.as_view(), name='internal_alumno'),
    path('internal/alumnos/<str:matricula>/por-matricula/', AlumnoPorMatriculaView.as_view(), name='internal_alumno_matricula'),
]
