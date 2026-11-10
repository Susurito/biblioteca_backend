from django.conf import settings
from django.db import connection
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from .auth import InternalOnly

class Health(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    def get(self, request):
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
        return Response({'status':'ok'})

class Metrics(APIView):
    authentication_classes = []
    permission_classes = [InternalOnly]
    def get(self, request):
        from .messaging import model
        oldest = model('Outbox').objects.filter(published_at__isnull=True).order_by('created_at').first()
        data = {'outbox_pendiente':model('Outbox').objects.filter(published_at__isnull=True).count(),
                'outbox_antiguedad_segundos':(timezone.now()-oldest.created_at).total_seconds() if oldest else 0,
                'mensajes_fallidos':model('FailedMessage').objects.filter(replayed_at__isnull=True).count()}
        if settings.SERVICE_NAME=='circulacion':
            qs = model('Saga').objects.exclude(estado__in=['completada','fallida'])
            oldest_saga = qs.order_by('creado').first()
            data.update(sagas_pendientes=qs.count(), saga_antiguedad_segundos=(timezone.now()-oldest_saga.creado).total_seconds() if oldest_saga else 0)
        return Response(data)
