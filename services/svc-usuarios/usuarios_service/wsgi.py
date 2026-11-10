"""WSGI config for usuarios_service."""
import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'usuarios_service.settings')
application = get_wsgi_application()
