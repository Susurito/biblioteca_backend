from django.urls import path, include
from rest_framework.routers import DefaultRouter
from catalogo.api import LibrosViewSet, InternalLibros, LegacyReserva, LegacyReservas, InternalAsignaciones
from biblioteca_common.views import Health, Metrics
router = DefaultRouter()
router.register('libros', LibrosViewSet, basename='libros')
urlpatterns = [path('health/', Health.as_view()), path('internal/metrics/', Metrics.as_view()),
               path('internal/asignaciones/', InternalAsignaciones.as_view()), path('internal/legacy-reservas/', LegacyReservas.as_view()), path('internal/legacy-reserva/', LegacyReserva.as_view()), path('internal/libros/', InternalLibros.as_view()), path('', include(router.urls))]
