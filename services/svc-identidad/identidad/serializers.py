"""Dominio de identidad: cuentas, roles, alumnos y administradores."""

from django.contrib.auth import get_user_model
from rest_framework import serializers
from identidad.models import Administradores, Alumnos

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    rol = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'rol']

    def get_rol(self, obj):
        if obj.groups.filter(name__iexact="alumno").exists():
            return 'alumno'
        elif obj.groups.filter(name__iexact="administrador").exists():
            return 'administrador'
        return 'sin_rol'


class AdminSerializer(serializers.ModelSerializer):
    first_name = serializers.CharField(source='user.first_name', read_only=True)
    last_name = serializers.CharField(source='user.last_name', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    username = serializers.CharField(source='user.username', read_only=True)
    is_active = serializers.BooleanField(source='user.is_active', read_only=True)

    class Meta:
        model = Administradores
        fields = [
            'id', 'matricula', 'first_name', 'last_name',
            'email', 'username', 'is_active', 'creado', 'actualizado'
        ]


class AlumnoSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source='user.email', read_only=True)
    username = serializers.CharField(source='user.username', read_only=True)
    is_active = serializers.BooleanField(source='user.is_active', read_only=True)
    user_id = serializers.IntegerField(source='user.id', read_only=True)

    class Meta:
        model = Alumnos
        fields = [
            'id', 'user_id', 'matricula', 'nombre',
            'apellido_paterno', 'apellido_materno', 'rol',
            'email', 'username', 'is_active', 'creado', 'actualizado'
        ]
