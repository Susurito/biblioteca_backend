"""
URLs de svc-auth.

Rutas expuestas públicamente (a través del API Gateway):
  POST /token/         → Login
  POST /custom-token/  → Alias de login (compatibilidad con frontend existente)
  GET  /logout/        → Logout (requiere token)

Rutas internas (solo entre servicios, proteger con firewall interno):
  GET  /validate/      → Validar token (para svc-libros, svc-prestamos, etc.)
"""

from django.urls import path
from auth_service.views.auth import CustomAuthToken, Logout, ValidateToken

urlpatterns = [
    # Endpoints de autenticación (compatibles con el monolito)
    path('token/', CustomAuthToken.as_view(), name='token_obtain'),
    path('custom-token/', CustomAuthToken.as_view(), name='custom_token'),
    path('logout/', Logout.as_view(), name='logout'),

    # Endpoint interno: validar token (NUEVO en svc-auth)
    path('validate/', ValidateToken.as_view(), name='validate_token'),
]
