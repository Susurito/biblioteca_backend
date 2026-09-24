from rest_framework import viewsets, permissions
from biblioteca_backend.models import Libros
from biblioteca_backend.serializers import LibrosSerializer

class LibrosViewSet(viewsets.ModelViewSet):
    queryset = Libros.objects.all()
    serializer_class = LibrosSerializer
    permission_classes = [permissions.AllowAny]
