import json
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from django.conf import settings
from rest_framework.exceptions import APIException

class DependencyUnavailable(APIException):
    status_code = 503
    default_detail = 'Servicio dependiente no disponible. Intenta de nuevo.'


def call(base, path, payload=None, token=None, method=None):
    headers = {'X-Service-Key': settings.INTERNAL_SERVICE_KEY, 'Content-Type': 'application/json'}
    if token:
        headers['Authorization'] = 'Token ' + token
    request = Request(base.rstrip('/') + path, headers=headers,
                      data=json.dumps(payload).encode() if payload is not None else None,
                      method=method or ('POST' if payload is not None else 'GET'))
    try:
        with urlopen(request, timeout=5) as response:
            return json.load(response)
    except HTTPError as exc:
        if exc.code in (400, 401, 403, 404, 409):
            try:
                detail = json.loads(exc.read())
            except ValueError:
                detail = {'detail': 'Error del servicio dependiente'}
            error = APIException(detail)
            error.status_code = exc.code
            raise error
        raise DependencyUnavailable() from exc
    except (URLError, TimeoutError, OSError, ValueError) as exc:
        raise DependencyUnavailable() from exc
