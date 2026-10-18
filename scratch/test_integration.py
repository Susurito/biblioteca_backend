import requests

# 1. Login as Admin
res_login = requests.post('http://127.0.0.1:8000/token/', json={'username': 'admi2@gmail.com', 'password': '123456'})
assert res_login.status_code == 200, f'Login failed: {res_login.text}'
token = res_login.json()['token']
headers = {'Authorization': f'Token {token}'}

# 2. Get Users
res_users = requests.get('http://127.0.0.1:8000/usuarios/', headers=headers)
assert res_users.status_code == 200, f'Get users failed: {res_users.text}'
users = res_users.json()
print(f'Total users received: {len(users)}')

# Find Luis Mora
luis = next((u for u in users if 'Luis' in u['nombre_completo']), None)
assert luis is not None, 'Luis Mora not found'
print(f"Luis Mora: {luis['nombre_completo']} | Matrícula: {luis['matricula']} | Estado: {luis['estado']} | Multas: {luis['multas_display']}")

# 3. Test Ficha de Luis Mora
res_ficha = requests.get(f"http://127.0.0.1:8000/usuarios/{luis['id']}/ficha/", headers=headers)
assert res_ficha.status_code == 200, f'Ficha failed: {res_ficha.text}'
ficha = res_ficha.json()
print(f"Sanciones de Luis Mora: {len(ficha['sanciones'])}")
for s in ficha['sanciones']:
    print(f"  - Libro: {s['libro_titulo']} | Retraso: {s['dias_retraso']} días | Multa: {s['multa_formateada']} | Pagada: {s['pagada']}")

# 4. Test Pagar Multa
res_pago = requests.post(f"http://127.0.0.1:8000/usuarios/{luis['id']}/pagar-multa/", json={}, headers=headers)
assert res_pago.status_code == 200, f'Pagar multa failed: {res_pago.text}'
print('Respuesta pago de multa:', res_pago.json()['message'])

# 5. Verify Luis Mora after payment
res_ficha_after = requests.get(f"http://127.0.0.1:8000/usuarios/{luis['id']}/ficha/", headers=headers)
ficha_after = res_ficha_after.json()
print(f"Luis Mora tras pago - Multas pendientes: {ficha_after['multas_display']}")
print('Sanción pagada?:', ficha_after['sanciones'][0]['pagada'], '| Fecha pago:', ficha_after['sanciones'][0]['fecha_pago'])

# 6. Reset test data for Luis Mora so it returns to pending fine for UI demonstration
from datetime import datetime, timedelta
from django.utils import timezone
import os, sys, django
sys.path.insert(0, os.path.abspath('.'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'biblioteca_backend.settings')
django.setup()
from biblioteca_backend.models import Prestamos
p = Prestamos.objects.filter(id=ficha['sanciones'][0]['prestamo_id']).first()
if p:
    p.multa_pagada = False
    p.fecha_pago_multa = None
    p.save()
    print('Reset Luis Mora fine back to unpaid ($60.00 MXN) for demonstration in frontend.')

print('ALL TESTS COMPLETED SUCCESSFULLY!')
