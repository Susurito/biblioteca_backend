"""
=============================================================================
Archivo de pruebas automatizadas y persistencia: test_reglas_devolucion.py
=============================================================================
Verificación de Reglas de Negocio en la Devolución de Libros:
1. Retraso 0 días: "Devolución a tiempo, sin sanción" (Multa: $0, Bloqueo: ------).
2. 1 a 7 días: Solo multa ($5.00 MXN por día, RN-03, sin bloqueo).
3. Más de 7 días: Multa ($5.00 MXN por día) + Bloqueo de 15 días (RN-04).

Este archivo ejecuta las pruebas contra la API real y GUARDA los préstamos
en la Base de Datos para que se puedan visualizar e interactuar directamente
en el Frontend (interfaz de Alumno y Administrador).

Ejecución:
  python test_reglas_devolucion.py
=============================================================================
"""

import os
import sys
import unittest
from datetime import timedelta
from django.utils import timezone

# Configurar entorno de Django
backend_dir = os.path.abspath(os.path.dirname(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'biblioteca_backend.settings')
import django
django.setup()

from django.contrib.auth.models import User
from rest_framework.test import APIClient
from rest_framework import status
from rest_framework.authtoken.models import Token
from biblioteca_backend.models import Alumnos, Administradores, Libros, Prestamos


class TestReglasDevolucion(unittest.TestCase):
    """
    Suite de pruebas usando unittest estándar para persistir los resultados
    en la base de datos MySQL real y no aplicar rollback.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.client = APIClient()

        # 1. Obtener Administrador con Token (admi2@gmail.com o admi@gmail.com)
        cls.admin_user = (
            User.objects.filter(username='admi2@gmail.com').first() or
            User.objects.filter(is_superuser=True).first() or
            User.objects.get(username='admi@gmail.com')
        )
        cls.admin_token, _ = Token.objects.get_or_create(user=cls.admin_user)
        cls.client.credentials(HTTP_AUTHORIZATION=f'Token {cls.admin_token.key}')

        # 2. Obtener Alumno principal (Gabriel Ramírez)
        cls.alumno = Alumnos.objects.filter(matricula='202248699').first() or Alumnos.objects.first()

        # 3. Libros para pruebas
        cls.libro_r1 = Libros.objects.filter(id=3).first() or Libros.objects.first()
        cls.libro_r2 = Libros.objects.filter(id=4).first() or Libros.objects.last()
        cls.libro_r3 = Libros.objects.filter(id=5).first() or Libros.objects.first()

    def test_01_regla_1_retraso_cero_a_tiempo(self):
        """
        REGLA 1:
        Retraso 0 días (A tiempo)
        - Días retraso : 0
        - Multa        : '$0'
        - Bloqueo      : '------'
        - Mensaje      : 'Devolución a tiempo, sin sanción'
        """
        ahora = timezone.now()
        prestamo = Prestamos.objects.create(
            alumno=self.alumno,
            libro=self.libro_r1,
            estado='aceptado',
            devuelto=False
        )
        Prestamos.objects.filter(id=prestamo.id).update(
            estado='aceptado',
            devuelto=False,
            fecha_solicitud=ahora - timedelta(days=2),
            fecha_vencimiento=ahora + timedelta(days=5),
            fecha_devolucion=None
        )
        prestamo.refresh_from_db()

        # Llamada al endpoint real del backend
        response = self.client.post(f'/prestamos/{prestamo.id}/devolver/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        detalles = response.data.get('detalles_devolucion', {})

        print("\n=======================================================")
        print(f"--- [TEST REGLA 1] Préstamo #{prestamo.id} (A tiempo - Retraso 0) ---")
        print(f"Alumno          : {detalles.get('alumno_nombre_completo')}")
        print(f"Libro           : {detalles.get('libro_titulo')}")
        print(f"Fecha Venc      : {detalles.get('fecha_vencimiento')}")
        print(f"Fecha Dev       : {detalles.get('fecha_devolucion')}")
        print(f"Días de retraso : {detalles.get('dias_retraso')}")
        print(f"Multa           : {detalles.get('multa')}")
        print(f"Bloqueo         : {detalles.get('bloqueo')}")
        print(f"Mensaje sanción : {detalles.get('mensaje_sancion')}")
        print("=======================================================")

        self.assertEqual(detalles.get('dias_retraso'), 0)
        self.assertEqual(detalles.get('multa'), "$0")
        self.assertEqual(detalles.get('bloqueo'), "------")
        self.assertIn("Devolución a tiempo, sin sanción", detalles.get('mensaje_sancion', ''))

        # Verificar persistencia en base de datos
        prestamo.refresh_from_db()
        self.assertTrue(prestamo.devuelto)
        self.assertIsNotNone(prestamo.fecha_devolucion)

        # Garantizar que quede un préstamo ACTIVO para la Regla 1 en el Frontend
        p_act1 = Prestamos.objects.filter(alumno=self.alumno, libro=self.libro_r1, devuelto=False).first()
        if not p_act1:
            p_act1 = Prestamos.objects.create(alumno=self.alumno, libro=self.libro_r1, estado='aceptado', devuelto=False)
        Prestamos.objects.filter(id=p_act1.id).update(
            estado='aceptado',
            devuelto=False,
            fecha_solicitud=ahora - timedelta(days=2),
            fecha_vencimiento=ahora + timedelta(days=5),
            fecha_devolucion=None
        )

    def test_02_regla_2_retraso_1_a_7_dias_solo_multa(self):
        """
        REGLA 2 (RN-03):
        Retraso 1 a 7 días (Simulando 4 días de retraso)
        - Días retraso : 4
        - Multa        : '$20.00 MXN' ($5.00 MXN x 4 días)
        - Bloqueo      : '------' (Sin bloqueo)
        - Mensaje      : Indica multa RN-03 sin bloqueo.
        """
        ahora = timezone.now()
        dias_retraso = 4

        prestamo = Prestamos.objects.create(
            alumno=self.alumno,
            libro=self.libro_r2,
            estado='aceptado',
            devuelto=False
        )
        Prestamos.objects.filter(id=prestamo.id).update(
            estado='aceptado',
            devuelto=False,
            fecha_solicitud=ahora - timedelta(days=11),
            fecha_vencimiento=ahora - timedelta(days=dias_retraso),
            fecha_devolucion=None
        )
        prestamo.refresh_from_db()

        # Llamada al endpoint real del backend
        response = self.client.post(f'/prestamos/{prestamo.id}/devolver/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        detalles = response.data.get('detalles_devolucion', {})

        multa_esperada = f"${(dias_retraso * 5.0):.2f} MXN"

        print("\n=======================================================")
        print(f"--- [TEST REGLA 2] Préstamo #{prestamo.id} (RN-03: Retraso {dias_retraso} días) ---")
        print(f"Alumno          : {detalles.get('alumno_nombre_completo')}")
        print(f"Libro           : {detalles.get('libro_titulo')}")
        print(f"Fecha Venc      : {detalles.get('fecha_vencimiento')}")
        print(f"Fecha Dev       : {detalles.get('fecha_devolucion')}")
        print(f"Días de retraso : {detalles.get('dias_retraso')}")
        print(f"Multa           : {detalles.get('multa')} (Esperado: {multa_esperada})")
        print(f"Bloqueo         : {detalles.get('bloqueo')} (Esperado: '------')")
        print(f"Mensaje sanción : {detalles.get('mensaje_sancion')}")
        print("=======================================================")

        self.assertEqual(detalles.get('dias_retraso'), dias_retraso)
        self.assertEqual(detalles.get('multa'), multa_esperada)
        self.assertEqual(detalles.get('bloqueo'), "------")
        self.assertIn("RN-03", detalles.get('mensaje_sancion', ''))

        # Verificar persistencia en base de datos
        prestamo.refresh_from_db()
        self.assertTrue(prestamo.devuelto)
        self.assertIsNotNone(prestamo.fecha_devolucion)

        # Garantizar que quede un préstamo ACTIVO para la Regla 2 en el Frontend
        p_act2 = Prestamos.objects.filter(alumno=self.alumno, libro=self.libro_r2, devuelto=False).first()
        if not p_act2:
            p_act2 = Prestamos.objects.create(alumno=self.alumno, libro=self.libro_r2, estado='aceptado', devuelto=False)
        Prestamos.objects.filter(id=p_act2.id).update(
            estado='aceptado',
            devuelto=False,
            fecha_solicitud=ahora - timedelta(days=11),
            fecha_vencimiento=ahora - timedelta(days=4),
            fecha_devolucion=None
        )

    def test_03_regla_3_mas_de_7_dias_multa_y_bloqueo(self):
        """
        REGLA 3 (RN-04):
        Retraso mayor a 7 días (Simulando 10 días de retraso)
        - Días retraso : 10
        - Multa        : '$50.00 MXN' ($5.00 MXN x 10 días)
        - Bloqueo      : 'Hasta el DD/MM/YYYY' (15 días de suspensión)
        - Mensaje      : Indica multa y bloqueo de 15 días (RN-04).
        """
        ahora = timezone.now()
        dias_retraso = 10

        prestamo = Prestamos.objects.create(
            alumno=self.alumno,
            libro=self.libro_r3,
            estado='aceptado',
            devuelto=False
        )
        Prestamos.objects.filter(id=prestamo.id).update(
            estado='aceptado',
            devuelto=False,
            fecha_solicitud=ahora - timedelta(days=17),
            fecha_vencimiento=ahora - timedelta(days=dias_retraso),
            fecha_devolucion=None
        )
        prestamo.refresh_from_db()

        # Llamada al endpoint real del backend
        response = self.client.post(f'/prestamos/{prestamo.id}/devolver/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        detalles = response.data.get('detalles_devolucion', {})

        multa_esperada = f"${(dias_retraso * 5.0):.2f} MXN"
        fecha_fin_bloqueo = ahora + timedelta(days=15)
        bloqueo_esperado = f"Hasta el {fecha_fin_bloqueo.strftime('%d/%m/%Y')}"

        print("\n=======================================================")
        print(f"--- [TEST REGLA 3] Préstamo #{prestamo.id} (RN-04: Retraso {dias_retraso} días) ---")
        print(f"Alumno          : {detalles.get('alumno_nombre_completo')}")
        print(f"Libro           : {detalles.get('libro_titulo')}")
        print(f"Fecha Venc      : {detalles.get('fecha_vencimiento')}")
        print(f"Fecha Dev       : {detalles.get('fecha_devolucion')}")
        print(f"Días de retraso : {detalles.get('dias_retraso')}")
        print(f"Multa           : {detalles.get('multa')} (Esperado: {multa_esperada})")
        print(f"Bloqueo         : {detalles.get('bloqueo')} (Esperado: '{bloqueo_esperado}')")
        print(f"Mensaje sanción : {detalles.get('mensaje_sancion')}")
        print("=======================================================")

        self.assertEqual(detalles.get('dias_retraso'), dias_retraso)
        self.assertEqual(detalles.get('multa'), multa_esperada)
        self.assertEqual(detalles.get('bloqueo'), bloqueo_esperado)
        self.assertIn("RN-04", detalles.get('mensaje_sancion', ''))

        # Verificar persistencia en base de datos
        prestamo.refresh_from_db()
        self.assertTrue(prestamo.devuelto)
        self.assertIsNotNone(prestamo.fecha_devolucion)

        # -------------------------------------------------------------
        # VERIFICACIÓN ESTRICTA RN-04:
        # Verificar que el backend BLOQUEA al alumno e impide nuevos préstamos
        # -------------------------------------------------------------
        client_alumno = APIClient()
        token_alumno, _ = Token.objects.get_or_create(user=self.alumno.user)
        client_alumno.credentials(HTTP_AUTHORIZATION=f'Token {token_alumno.key}')

        resp_bloqueo = client_alumno.post('/solicitar-prestamo/', {'libro': self.libro_r1.id})
        self.assertEqual(resp_bloqueo.status_code, status.HTTP_400_BAD_REQUEST)
        error_msg = str(resp_bloqueo.data.get('error', ''))
        self.assertTrue(resp_bloqueo.data.get('bloqueado', False))
        self.assertIn("RN-04", error_msg)
        print(f"\n>>> [VERIFICACIÓN RN-04 BLOQUEO] El alumno fue bloqueado correctamente para solicitar préstamos:")
        print(f"    Respuesta HTTP : 400 Bad Request")
        print(f"    Bloqueado      : {resp_bloqueo.data.get('bloqueado')}")
        print(f"    Mensaje        : '{error_msg}'")

        # Garantizar que quede un préstamo ACTIVO para la Regla 3 en el Frontend
        p_act3 = Prestamos.objects.filter(alumno=self.alumno, libro=self.libro_r3, devuelto=False).first()
        if not p_act3:
            p_act3 = Prestamos.objects.create(alumno=self.alumno, libro=self.libro_r3, estado='aceptado', devuelto=False)
        Prestamos.objects.filter(id=p_act3.id).update(
            estado='aceptado',
            devuelto=False,
            fecha_solicitud=ahora - timedelta(days=17),
            fecha_vencimiento=ahora - timedelta(days=10),
            fecha_devolucion=None
        )


def sembrar_prestamos_activos_para_el_frontend():
    """
    Garantiza que queden préstamos ACTIVOS en la base de datos para las 3 reglas:
    1. Préstamo a tiempo (Regla 1)
    2. Préstamo vencido hace 4 días (Regla 2, RN-03)
    3. Préstamo vencido hace 10 días (Regla 3, RN-04)
    Para que el usuario pueda abrir el panel de Administrador en el frontend (/admin)
    y presionar en vivo el botón 'Devolver' de cualquiera de ellos y ver el modal.
    """
    ahora = timezone.now()
    alumno = Alumnos.objects.filter(matricula='202248699').first() or Alumnos.objects.first()
    l_r1 = Libros.objects.filter(id=3).first() or Libros.objects.first()
    l_r2 = Libros.objects.filter(id=4).first() or Libros.objects.last()
    l_r3 = Libros.objects.filter(id=5).first() or Libros.objects.first()

    # Préstamo Activo 1: A tiempo (Vence en 5 días)
    p_act1 = Prestamos.objects.filter(alumno=alumno, libro=l_r1, devuelto=False).first()
    if not p_act1:
        p_act1 = Prestamos.objects.create(alumno=alumno, libro=l_r1, estado='aceptado', devuelto=False)
    Prestamos.objects.filter(id=p_act1.id).update(
        estado='aceptado',
        devuelto=False,
        fecha_solicitud=ahora - timedelta(days=2),
        fecha_vencimiento=ahora + timedelta(days=5),
        fecha_devolucion=None
    )

    # Préstamo Activo 2: Con 4 días de retraso (RN-03)
    p_act2 = Prestamos.objects.filter(alumno=alumno, libro=l_r2, devuelto=False).first()
    if not p_act2:
        p_act2 = Prestamos.objects.create(alumno=alumno, libro=l_r2, estado='aceptado', devuelto=False)
    Prestamos.objects.filter(id=p_act2.id).update(
        estado='aceptado',
        devuelto=False,
        fecha_solicitud=ahora - timedelta(days=11),
        fecha_vencimiento=ahora - timedelta(days=4),
        fecha_devolucion=None
    )

    # Préstamo Activo 3: Con 10 días de retraso (RN-04)
    p_act3 = Prestamos.objects.filter(alumno=alumno, libro=l_r3, devuelto=False).first()
    if not p_act3:
        p_act3 = Prestamos.objects.create(alumno=alumno, libro=l_r3, estado='aceptado', devuelto=False)
    Prestamos.objects.filter(id=p_act3.id).update(
        estado='aceptado',
        devuelto=False,
        fecha_solicitud=ahora - timedelta(days=17),
        fecha_vencimiento=ahora - timedelta(days=10),
        fecha_devolucion=None
    )

    print("\n*****************************************************************")
    print(">>> DATOS GUARDADOS EN LA BD LISTOS PARA EL FRONTEND (REGLAS 1, 2 Y 3) <<<")
    print(f"• [Regla 1 - A tiempo] ID #{p_act1.id:2d}: '{l_r1.titulo}' (Vence en 5 días)")
    print(f"• [Regla 2 - RN-03]    ID #{p_act2.id:2d}: '{l_r2.titulo}' (Vencido hace 4 días)")
    print(f"• [Regla 3 - RN-04]    ID #{p_act3.id:2d}: '{l_r3.titulo}' (Vencido hace 10 días)")
    print("-----------------------------------------------------------------")
    print("CÓMO VISUALIZARLO EN EL FRONTEND:")
    print("1. Inicia sesión como Administrador en http://localhost:4200/login (admi2@gmail.com / 123456)")
    print("2. Ve a la sección 'Préstamos' (http://localhost:4200/admin) -> 'Préstamos Activos':")
    print(f"   - Préstamo #{p_act1.id} (A tiempo): Al pulsar 'Devolver' -> Modal: 'Devolución a tiempo, sin sanción'.")
    print(f"   - Préstamo #{p_act2.id} (RN-03, 4 días): Al pulsar 'Devolver' -> Modal: Multa $20.00 MXN y Bloqueo '------'.")
    print(f"   - Préstamo #{p_act3.id} (RN-04, 10 días): Al pulsar 'Devolver' -> Modal: Multa $50.00 MXN y Bloqueo de 15 días.")
    print("3. En la pestaña 'Historial de Préstamos' verás las devoluciones ya procesadas de cada regla.")
    print("*****************************************************************\n")


if __name__ == '__main__':
    # 1. Ejecutar suite de pruebas de las 3 reglas
    suite = unittest.TestLoader().loadTestsFromTestCase(TestReglasDevolucion)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # 2. Sembrar préstamos activos interactivos para la interfaz web
    sembrar_prestamos_activos_para_el_frontend()

    sys.exit(not result.wasSuccessful())
