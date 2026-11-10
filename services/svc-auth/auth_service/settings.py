"""
Settings para svc-auth — Microservicio de Autenticación.
Solo gestiona tokens y sesiones. No tiene modelos propios de negocio;
consulta svc-usuarios via HTTP para resolver usuarios y roles.
"""
import os
from datetime import timedelta

# ──────────────────────────────────────────────
# SEGURIDAD — La misma SECRET_KEY que el monolito
# para que los tokens sean inter-operables durante la migración
# ──────────────────────────────────────────────
SECRET_KEY = os.environ.get(
    'DJANGO_SECRET_KEY',
    'solo-para-desarrollo-local-nunca-usar-en-produccion'
)
DEBUG = os.environ.get('DJANGO_DEBUG', 'False') == 'True'
ALLOWED_HOSTS = ['*']

# ──────────────────────────────────────────────
# APLICACIONES
# ──────────────────────────────────────────────
INSTALLED_APPS = [
    'django.contrib.contenttypes',
    'django.contrib.auth',
    'rest_framework',
    'rest_framework.authtoken',
    'corsheaders',
    'auth_service',
]

# ──────────────────────────────────────────────
# MIDDLEWARE
# ──────────────────────────────────────────────
MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.middleware.common.CommonMiddleware',
]

CORS_ALLOW_ALL_ORIGINS = True  # En producción, restringir a los servicios internos

# ──────────────────────────────────────────────
# URLs & WSGI
# ──────────────────────────────────────────────
ROOT_URLCONF = 'auth_service.urls'
WSGI_APPLICATION = 'auth_service.wsgi.application'

# ──────────────────────────────────────────────
# BASE DE DATOS
# svc-auth solo necesita la tabla authtoken_token y auth_user
# ──────────────────────────────────────────────
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': os.environ.get('DB_NAME', 'auth_db'),
        'USER': os.environ.get('DB_USER', 'root'),
        'PASSWORD': os.environ.get('DB_PASSWORD', 'rootpassword'),
        'HOST': os.environ.get('DB_HOST', 'db-auth'),
        'PORT': os.environ.get('DB_PORT', '3306'),
        'OPTIONS': {
            'charset': 'utf8mb4',
        },
    }
}

# ──────────────────────────────────────────────
# DRF
# ──────────────────────────────────────────────
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.TokenAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=1),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=1),
    'AUTH_HEADER_TYPES': ('Bearer',),
}

# ──────────────────────────────────────────────
# URLs de otros servicios (para consultas internas)
# ──────────────────────────────────────────────
USUARIOS_SERVICE_URL = os.environ.get('USUARIOS_SERVICE_URL', 'http://svc-usuarios:8002')

# ──────────────────────────────────────────────
# INTERNACIONALIZACIÓN
# ──────────────────────────────────────────────
LANGUAGE_CODE = 'es-mx'
TIME_ZONE = 'America/Mexico_City'
USE_I18N = True
USE_TZ = True

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
