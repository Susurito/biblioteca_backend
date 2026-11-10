from rest_framework.permissions import BasePermission
from .models import Administradores

class AdminOnly(BasePermission):
    def has_permission(self,request,view):
        user=request.user
        return bool(user and user.is_authenticated and (user.is_superuser or
            user.groups.filter(name__iexact='administrador').exists() or
            user.groups.filter(name__iexact='admin').exists() or
            Administradores.objects.filter(user=user).exists()))
