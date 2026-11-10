import hmac
from dataclasses import dataclass
from django.conf import settings
from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.permissions import BasePermission
from .http import call

@dataclass
class Principal:
    id: int
    username: str
    rol: str
    alumno_id: object = None
    is_active: bool = True
    is_superuser: bool = False

    @property
    def pk(self):
        return self.id

    @property
    def is_authenticated(self):
        return self.is_active

class RemoteTokenAuthentication(BaseAuthentication):
    def authenticate_header(self, request):
        return 'Token'

    def authenticate(self, request):
        parts = get_authorization_header(request).split()
        if not parts:
            return None
        if len(parts) != 2 or parts[0].lower() != b'token':
            raise AuthenticationFailed('Usa Authorization: Token <token>.')
        try:
            token = parts[1].decode('ascii')
        except UnicodeError:
            raise AuthenticationFailed('Token inválido.')
        data = call(settings.IDENTITY_URL, '/internal/validate/', token=token)
        return Principal(**{k: data[k] for k in Principal.__dataclass_fields__ if k in data}), token

class InternalOnly(BasePermission):
    def has_permission(self, request, view):
        expected = settings.INTERNAL_SERVICE_KEY
        supplied = request.headers.get('X-Service-Key', '')
        return bool(expected and hmac.compare_digest(supplied, expected))

class IsAdmin(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and (
            request.user.is_superuser or getattr(request.user, 'rol', '') == 'administrador'))

class AdminOrReadOnly(IsAdmin):
    def has_permission(self, request, view):
        return request.method in ('GET', 'HEAD', 'OPTIONS') or super().has_permission(request, view)
