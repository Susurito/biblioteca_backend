from django.urls import path, include
from rest_framework.routers import DefaultRouter
from circulacion.api import PrestamosViewSet, OperacionView, InternalResumenes, InternalHistorial, InternalPago
from biblioteca_common.views import Health, Metrics
router=DefaultRouter()
router.register('prestamos', PrestamosViewSet, basename='prestamos')
urlpatterns = [path('health/',Health.as_view()), path('internal/metrics/',Metrics.as_view()),
    path('solicitar-prestamo/',PrestamosViewSet.as_view({'post':'create'})),
    path('operaciones/<uuid:pk>/',OperacionView.as_view()),
    path('internal/resumenes/',InternalResumenes.as_view()), path('internal/historial/',InternalHistorial.as_view()),
    path('internal/pagar-multa/',InternalPago.as_view()), path('',include(router.urls))]
