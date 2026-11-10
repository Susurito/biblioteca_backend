"""Run inside the isolated loans container, against real HTTP, MySQL and RabbitMQ.

Seed integration-admin first using the documented command. Never use this on real data.
"""
import json
import sys
sys.path.insert(0, '/app')
import time
import uuid
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from urllib.request import Request, urlopen
from urllib.error import HTTPError

BASE = 'http://nginx'
ADMIN_PASSWORD = 'IntegrationPassword123'


def api(method, path, body=None, token=None, headers=None):
    hdr = {'Content-Type': 'application/json', **(headers or {})}
    if token:
        hdr['Authorization'] = 'Token ' + token
    req = Request(BASE+path, method=method, headers=hdr,
                  data=json.dumps(body).encode() if body is not None else None)
    try:
        with urlopen(req, timeout=15) as response:
            return response.status, json.load(response)
    except HTTPError as exc:
        raw=exc.read()
        try:
            payload=json.loads(raw)
        except ValueError:
            payload=raw.decode()
        return exc.code,payload


def wait_operation(op, token):
    deadline=time.monotonic()+90
    while time.monotonic()<deadline:
        status,data=api('GET','/operaciones/'+op+'/',token=token)
        assert status==200,(status,data)
        if data['estado'] in ('completada','fallida'):
            return data
        time.sleep(.25)
    raise AssertionError('Saga sin completar: '+op)


class EndToEnd(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        status, data = api('POST','/token/',{'username':'integration-admin','password':ADMIN_PASSWORD})
        assert status==200,(status,data)
        cls.admin=data['token']

    def student(self):
        suffix=uuid.uuid4().hex[:8]
        email='a'+suffix+'@example.com'
        status,data=api('POST','/register/',dict(email=email,nombre='Ana',password=ADMIN_PASSWORD,
                         tipo='alumno',matricula=suffix,apellido_paterno='Pérez'))
        self.assertEqual(status,201,data)
        status,data=api('POST','/token/',dict(username=email,password=ADMIN_PASSWORD))
        self.assertEqual(status,200,data)
        return data

    def book(self, copies=1):
        status,data=api('POST','/libros/',dict(titulo='Libro '+uuid.uuid4().hex[:8],autor='Autor',genero='Software',total_ejemplares=copies),self.admin)
        self.assertEqual(status,201,data)
        return data

    def request(self, student, book):
        status,data=api('POST','/solicitar-prestamo/',{'libro':book['id']},student['token'])
        self.assertEqual(status,201,data)
        return data

    def test_01_complete_flow_and_penalty_payment(self):
        student=self.student(); book=self.book()
        loan=self.request(student,book)
        status,op=api('POST',f"/prestamos/{loan['id']}/aprobar/",{},self.admin)
        self.assertEqual(status,202,op)
        status,repeated=api('POST',f"/prestamos/{loan['id']}/aprobar/",{},self.admin)
        self.assertEqual(repeated['operacion_id'],op['operacion_id'])
        self.assertEqual(wait_operation(op['operacion_id'],self.admin)['estado'],'completada')
        # This runs only in the isolated loans database, never via a public mutation bypass.
        import os
        os.environ.setdefault('DJANGO_SETTINGS_MODULE','prestamos_service.settings')
        import django
        django.setup()
        from circulacion.models import Prestamo
        from django.utils import timezone
        Prestamo.objects.filter(pk=loan['id']).update(fecha_vencimiento=timezone.now()-timedelta(days=10))
        status,op=api('POST',f"/prestamos/{loan['id']}/devolver/",{},self.admin)
        self.assertEqual(status,202,op)
        result=wait_operation(op['operacion_id'],self.admin)
        self.assertEqual(result['estado'],'completada')
        self.assertEqual(result['resultado']['detalles_devolucion']['multa'],'$50.00 MXN')
        status,profile=api('GET','/perfil/',token=student['token'])
        self.assertEqual(status,200,profile)
        self.assertTrue(profile['bloqueado'])
        self.assertEqual(profile['user_id'],student['user_id'])
        status,payment=api('POST',f"/usuarios/{student['user_id']}/pagar-multa/",{},self.admin)
        self.assertEqual(status,200,payment)
        self.assertEqual(payment['total_pagado'],'$50.00 MXN')
        status,payment=api('POST',f"/usuarios/{student['user_id']}/pagar-multa/",{},self.admin)
        self.assertEqual(payment['total_pagado'],'$0.00 MXN')
        self.assertTrue(payment['usuario']['bloqueado'])
        status,book=api('GET',f"/libros/{book['id']}/")
        self.assertEqual(book['disponibles'],1)
        self.assertEqual(api('GET','/internal/metrics/',headers={'X-Service-Key':'IntegrationTestOnlySecret123456'})[0],404)
        self.assertEqual(api('POST','/logout/',{},student['token'])[0],200)
        self.assertEqual(api('GET','/perfil/',token=student['token'])[0],401)

    def test_02_concurrent_approvals_of_last_copy(self):
        book=self.book()
        loans=[self.request(self.student(),book) for _ in range(2)]
        with ThreadPoolExecutor(max_workers=2) as pool:
            ops=list(pool.map(lambda loan:api('POST',f"/prestamos/{loan['id']}/aprobar/",{},self.admin),loans))
        self.assertTrue(all(status==202 for status,op in ops),ops)
        states=[wait_operation(op['operacion_id'],self.admin)['estado'] for _,op in ops]
        self.assertEqual(sorted(states),['completada','fallida'])
        status,book=api('GET',f"/libros/{book['id']}/")
        self.assertEqual(book['disponibles'],0)
        self.assertEqual(book['prestados'],1)

    def test_03_concurrent_student_limit(self):
        student=self.student()
        loans=[self.request(student,self.book()) for _ in range(4)]
        with ThreadPoolExecutor(max_workers=4) as pool:
            responses=list(pool.map(lambda p:api('POST',f"/prestamos/{p['id']}/aprobar/",{},self.admin),loans))
        self.assertEqual(sorted(status for status,data in responses),[202,202,202,400],responses)
        for status,data in responses:
            if status==202:
                self.assertEqual(wait_operation(data['operacion_id'],self.admin)['estado'],'completada')
        status,profile=api('GET','/perfil/',token=student['token'])
        self.assertEqual(profile['prestamos_activos'],3)

    def test_04_permissions(self):
        student=self.student(); book=self.book()
        loan=self.request(student,book)
        self.assertEqual(api('POST',f"/prestamos/{loan['id']}/aprobar/",{},student['token'])[0],403)
        self.assertEqual(api('POST','/admin/create/',{},student['token'])[0],403)
        self.assertEqual(api('PATCH',f"/prestamos/{loan['id']}/",{'devuelto':True},student['token'])[0],403)
        self.assertEqual(api('POST','/libros/',{},student['token'])[0],403)
        self.assertEqual(api('POST',f"/usuarios/{student['user_id']}/desactivar/",{},self.admin)[0],200)
        self.assertEqual(api('GET','/perfil/',token=student['token'])[0],401)

if __name__=='__main__':
    unittest.main(verbosity=2)
