import os
import sys
import django
from datetime import datetime, timedelta

sys.path.insert(0, os.path.abspath('.'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'biblioteca_backend.settings')
django.setup()

from django.contrib.auth.models import User, Group
from django.utils import timezone
from biblioteca_backend.models import Alumnos, Prestamos, Libros

grupo_alumno, _ = Group.objects.get_or_create(name='alumno')
libros = list(Libros.objects.all())

# 1. Ana López
u1, _ = User.objects.get_or_create(username='ana@alumno.buap.mx', defaults={'email': 'ana@alumno.buap.mx'})
u1.email = 'ana@alumno.buap.mx'
u1.first_name = 'Ana'
u1.last_name = 'López'
u1.is_active = True
u1.set_password('123456')
u1.save()
grupo_alumno.user_set.add(u1)

a1, _ = Alumnos.objects.get_or_create(user=u1, defaults={'matricula': '202312345'})
a1.nombre = 'Ana'
a1.apellido_paterno = 'López'
a1.apellido_materno = ''
a1.matricula = '202312345'
a1.rol = 'Estudiante'
a1.save()

# Ana has 1 active loan
Prestamos.objects.filter(alumno=a1).delete()
Prestamos.objects.create(
    alumno=a1,
    libro=libros[0],
    fecha_solicitud=timezone.now() - timedelta(days=2),
    fecha_vencimiento=timezone.now() + timedelta(days=5),
    estado='aceptado',
    devuelto=False
)

# 2. Luis Mora (Bloqueado hasta 21/10)
u2, _ = User.objects.get_or_create(username='luis@alumno.buap.mx', defaults={'email': 'luis@alumno.buap.mx'})
u2.email = 'luis@alumno.buap.mx'
u2.first_name = 'Luis'
u2.last_name = 'Mora'
u2.is_active = True
u2.set_password('123456')
u2.save()
grupo_alumno.user_set.add(u2)

a2, _ = Alumnos.objects.get_or_create(user=u2, defaults={'matricula': '202298765'})
a2.nombre = 'Luis'
a2.apellido_paterno = 'Mora'
a2.apellido_materno = ''
a2.matricula = '202298765'
a2.rol = 'Estudiante'
a2.save()

# Luis has 0 active loans, but 1 returned loan on 2026-10-06 with > 7 days delay => suspension until 2026-10-21
Prestamos.objects.filter(alumno=a2).delete()
f_dev = timezone.make_aware(datetime(2026, 10, 6, 12, 0, 0))
f_venc = f_dev - timedelta(days=12) # 12 days delay (> 7)
f_sol = f_venc - timedelta(days=7)
p2 = Prestamos.objects.create(
    alumno=a2,
    libro=libros[1] if len(libros) > 1 else libros[0],
    fecha_solicitud=f_sol,
    fecha_vencimiento=f_venc,
    fecha_devolucion=f_dev,
    estado='aceptado',
    devuelto=True,
    multa_pagada=False
)

# 3. Dr. Juan Pérez
u3, _ = User.objects.get_or_create(username='jperez@buap.mx', defaults={'email': 'jperez@buap.mx'})
u3.email = 'jperez@buap.mx'
u3.first_name = 'Dr. Juan'
u3.last_name = 'Pérez'
u3.is_active = True
u3.set_password('123456')
u3.save()
grupo_alumno.user_set.add(u3)

a3, _ = Alumnos.objects.get_or_create(user=u3, defaults={'matricula': 'D-1002'})
a3.nombre = 'Dr. Juan'
a3.apellido_paterno = 'Pérez'
a3.apellido_materno = ''
a3.matricula = 'D-1002'
a3.rol = 'Docente'
a3.save()

# Juan has 2 active loans out of 5
Prestamos.objects.filter(alumno=a3).delete()
Prestamos.objects.create(
    alumno=a3,
    libro=libros[0],
    fecha_solicitud=timezone.now() - timedelta(days=1),
    fecha_vencimiento=timezone.now() + timedelta(days=13),
    estado='aceptado',
    devuelto=False
)
if len(libros) > 1:
    Prestamos.objects.create(
        alumno=a3,
        libro=libros[1],
        fecha_solicitud=timezone.now() - timedelta(days=3),
        fecha_vencimiento=timezone.now() + timedelta(days=11),
        estado='aceptado',
        devuelto=False
    )

# 4. Carlos Ruiz (Inactivo)
u4, _ = User.objects.get_or_create(username='cruiz@alumno.buap.mx', defaults={'email': 'cruiz@alumno.buap.mx'})
u4.email = 'cruiz@alumno.buap.mx'
u4.first_name = 'Carlos'
u4.last_name = 'Ruiz'
u4.is_active = False # Inactivo
u4.set_password('123456')
u4.save()
grupo_alumno.user_set.add(u4)

a4, _ = Alumnos.objects.get_or_create(user=u4, defaults={'matricula': '201900001'})
a4.nombre = 'Carlos'
a4.apellido_paterno = 'Ruiz'
a4.apellido_materno = ''
a4.matricula = '201900001'
a4.rol = 'Estudiante'
a4.save()
Prestamos.objects.filter(alumno=a4).delete()

print("Mock users seeded successfully!")
