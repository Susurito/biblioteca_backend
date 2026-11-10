from django.db import IntegrityError
from rest_framework.views import exception_handler
from rest_framework.response import Response

def handler(exc, context):
    if isinstance(exc, IntegrityError):
        return Response({'detail':'El registro entra en conflicto con datos existentes.'},status=409)
    return exception_handler(exc, context)
