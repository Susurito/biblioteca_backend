# biblioteca_backend/views/__init__.py
from .views import (
    LibrosViewSet,
    PrestamosViewSet, 
    SolicitarPrestamoView,
    UserSerializer,
    AdminSerializer,
    AlumnoSerializer,
    LibrosSerializer,
    PrestamosSerializer
)

__all__ = [
    'LibrosViewSet',
    'PrestamosViewSet',
    'SolicitarPrestamoView',
    'UserSerializer',
    'AdminSerializer', 
    'AlumnoSerializer',
    'LibrosSerializer',
    'PrestamosSerializer'
]