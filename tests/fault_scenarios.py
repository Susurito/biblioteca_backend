"""Run in the isolated loans container before/after stopping RabbitMQ or its worker."""
import sys
sys.path[:0]=['/app','/tmp']
import json
import time
import uuid
from pathlib import Path
from e2e import api,wait_operation,ADMIN_PASSWORD

state_path=Path('/tmp/biblioteca-fault-state.json')
phase=sys.argv[1]
if phase=='start':
    suffix=uuid.uuid4().hex[:8]
    status,admin=api('POST','/token/',{'username':'integration-admin','password':ADMIN_PASSWORD})
    assert status==200,(status,admin)
    token=admin['token']
    email=suffix+'@example.com'
    status,row=api('POST','/register/',dict(email=email,nombre='Recovery',password=ADMIN_PASSWORD,tipo='alumno',matricula=suffix))
    assert status==201,(status,row)
    status,student=api('POST','/token/',dict(username=email,password=ADMIN_PASSWORD))
    assert status==200,(status,student)
    status,book=api('POST','/libros/',dict(titulo='Recovery '+suffix,autor='Autor',genero='Software',total_ejemplares=1),token)
    assert status==201,(status,book)
    status,loan=api('POST','/solicitar-prestamo/',{'libro':book['id']},student['token'])
    assert status==201,(status,loan)
    status,op=api('POST',f"/prestamos/{loan['id']}/aprobar/",{},token)
    assert status==202,(status,op)
    status,repeated=api('POST',f"/prestamos/{loan['id']}/aprobar/",{},token)
    assert repeated['operacion_id']==op['operacion_id']
    time.sleep(2)
    status,op_state=api('GET','/operaciones/'+op['operacion_id']+'/',token=token)
    assert op_state['estado']=='reservando',op_state
    status,loan_state=api('GET',f"/prestamos/{loan['id']}/",token=token)
    assert loan_state['estado']=='pendiente',loan_state
    state_path.write_text(json.dumps(dict(token=token,book=book,loan=loan,op=op)))
    print('PASS: operación durable pendiente, sin falso aprobado ni Saga duplicada.')
elif phase=='finish':
    state=json.loads(state_path.read_text())
    token,loan,book,op=[state[k] for k in ('token','loan','book','op')]
    assert wait_operation(op['operacion_id'],token)['estado']=='completada'
    # Duplicate delivery with the same ID and replay with a new ID are both harmless.
    import os
    os.environ.setdefault('DJANGO_SETTINGS_MODULE','prestamos_service.settings')
    import django
    django.setup()
    import pika
    from django.conf import settings
    from biblioteca_common.messaging import publish,topology
    from circulacion.models import Saga,Outbox
    saga=Saga.objects.get(pk=op['operacion_id'])
    assert Saga.objects.filter(prestamo_id=loan['id'],tipo='aprobar').count()==1
    messages=list(Outbox.objects.filter(body__saga_id=str(saga.pk)).order_by('created_at'))
    connection=pika.BlockingConnection(pika.URLParameters(settings.RABBITMQ_URL))
    channel=connection.channel()
    topology(channel)
    for row in messages:
        publish(channel,row.routing_key,row.body)
        body=dict(row.body,message_id=str(uuid.uuid4()))
        publish(channel,row.routing_key,body)
    time.sleep(2)
    status,current=api('GET',f"/libros/{book['id']}/")
    assert current['prestados']==1 and current['disponibles']==0,current
    status,returned=api('POST',f"/prestamos/{loan['id']}/devolver/",{},token)
    assert status==202,(status,returned)
    assert wait_operation(returned['operacion_id'],token)['estado']=='completada'
    # Late reserve and confirm must never resurrect the allocation after return.
    for row in messages:
        publish(channel,row.routing_key,dict(row.body,message_id=str(uuid.uuid4())))
    time.sleep(2)
    status,current=api('GET',f"/libros/{book['id']}/")
    assert current['prestados']==0 and current['disponibles']==1,current
    connection.close()
    print('PASS: recuperación, duplicados y comandos tardíos; una sola asignación y liberación.')
else:
    raise SystemExit('Use start o finish')
