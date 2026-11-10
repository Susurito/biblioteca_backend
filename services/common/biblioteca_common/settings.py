import os

def configure(service, app, identity=False):
    test = os.getenv('SQLITE_TEST') == '1'
    database = {'ENGINE': 'django.db.backends.sqlite3', 'NAME': os.getenv('SQLITE_PATH', ':memory:')} if test else {
        'ENGINE': 'django.db.backends.mysql', 'NAME': os.environ['DB_NAME'],
        'USER': os.environ['DB_USER'], 'PASSWORD': os.environ['DB_PASSWORD'],
        'HOST': os.environ['DB_HOST'], 'PORT': '3306',
        'OPTIONS': {'charset': 'utf8mb4', 'isolation_level': 'read committed'},
    }
    return dict(
        SECRET_KEY=os.getenv('DJANGO_SECRET_KEY', 'development-only-service-key'),
        DEBUG=False, ALLOWED_HOSTS=['*'], ROOT_URLCONF=service+'.urls',
        INSTALLED_APPS=['django.contrib.auth', 'django.contrib.contenttypes',
                        'rest_framework', 'corsheaders'] + (['rest_framework.authtoken'] if identity else []) + [app],
        MIDDLEWARE=['corsheaders.middleware.CorsMiddleware', 'django.middleware.common.CommonMiddleware'],
        CORS_ALLOWED_ORIGINS=['http://localhost:4200', 'http://127.0.0.1:4200'],
        DATABASES={'default': database}, USE_TZ=True, TIME_ZONE='America/Mexico_City',
        LANGUAGE_CODE='es-mx', DEFAULT_AUTO_FIELD='django.db.models.BigAutoField',
        INTERNAL_SERVICE_KEY=os.getenv('INTERNAL_SERVICE_KEY', ''),
        IDENTITY_URL=os.getenv('IDENTITY_URL', 'http://svc-identidad:8001'),
        LOANS_URL=os.getenv('LOANS_URL', 'http://svc-prestamos:8004'),
        BOOKS_URL=os.getenv('BOOKS_URL', 'http://svc-libros:8003'),
        RABBITMQ_URL=os.getenv('RABBITMQ_URL', ''),
        SERVICE_NAME=app,
        LEGACY_CATALOG_ENABLED=os.getenv('LEGACY_CATALOG_ENABLED', '1') == '1',
        LOGGING={'version':1, 'disable_existing_loggers':False,
                 'handlers':{'console':{'class':'logging.StreamHandler'}},
                 'loggers':{'biblioteca_common':{'handlers':['console'],'level':'INFO','propagate':False}}},
        REST_FRAMEWORK={
            'EXCEPTION_HANDLER':'biblioteca_common.exceptions.handler',
            'DEFAULT_AUTHENTICATION_CLASSES': [
                'rest_framework.authentication.TokenAuthentication' if identity else
                'biblioteca_common.auth.RemoteTokenAuthentication'],
            'DEFAULT_PERMISSION_CLASSES': ['rest_framework.permissions.IsAuthenticated'],
            'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
            'PAGE_SIZE': 100,
        },
    )
