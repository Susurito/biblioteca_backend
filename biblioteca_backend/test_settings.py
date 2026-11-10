from biblioteca_common.settings import configure
globals().update(configure('biblioteca_backend', 'biblioteca_backend', identity=True))
CATALOG_REMOTE_ENABLED = False
REST_FRAMEWORK['DEFAULT_AUTHENTICATION_CLASSES']=['rest_framework.authentication.TokenAuthentication']
