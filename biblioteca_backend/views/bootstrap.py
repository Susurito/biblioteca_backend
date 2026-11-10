from rest_framework import generics
from rest_framework.response import Response

class VersionView(generics.GenericAPIView):
    def get(self, request, *args, **kwargs):
        return Response({'version': '1.0.0'})
