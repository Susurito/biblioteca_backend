# biblioteca_backend/views/__init__.py
from .views import (
    LibrosViewSet,
    PrestamosViewSet,
    SolicitarPrestamoView,
    verificar_bloqueo_alumno,
)
from biblioteca_backend.serializers import (
    UserSerializer,
    AdminSerializer,
    AlumnoSerializer,
    LibrosSerializer,
    PrestamosSerializer,
)

__all__ = [
    'LibrosViewSet',
    'PrestamosViewSet',
    'SolicitarPrestamoView',
    'verificar_bloqueo_alumno',
    'UserSerializer',
    'AdminSerializer',
    'AlumnoSerializer',
    'LibrosSerializer',
    'PrestamosSerializer',
]