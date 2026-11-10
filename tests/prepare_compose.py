"""Build an isolated test topology, without source DBs, monolith, or real credentials."""
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
config = json.loads(subprocess.check_output(['docker','compose','config','--format','json'],cwd=ROOT))
keep = {'nginx','svc-identidad','svc-libros','svc-prestamos','worker-libros','worker-prestamos',
        'db-identidad','db-libros','db-prestamos','rabbitmq'}
config['services'] = {k:v for k,v in config['services'].items() if k in keep}
for name, service in config['services'].items():
    env = service.get('environment',{})
    for key in list(env):
        if 'PASSWORD' in key or key in ('RABBITMQ_DEFAULT_PASS','INTERNAL_SERVICE_KEY','DJANGO_SECRET_KEY'):
            env[key] = 'IntegrationTestOnlySecret123456'
    if 'RABBITMQ_URL' in env:
        env['RABBITMQ_URL'] = 'amqp://biblioteca:IntegrationTestOnlySecret123456@rabbitmq:5672/%2F'
    if 'LOANS_URL' in env:
        env['LOANS_URL'] = 'http://svc-prestamos:8004'
    service.pop('container_name',None)
    service.pop('ports',None)
config['services']['nginx']['environment'].update(IDENTITY_UPSTREAM='svc-identidad:8001',
    BOOKS_UPSTREAM='svc-libros:8003',LOANS_UPSTREAM='svc-prestamos:8004',FALLBACK_UPSTREAM='svc-identidad:8001')
config['services']['nginx']['depends_on'] = {k:{'condition':'service_healthy'} for k in ('svc-identidad','svc-libros','svc-prestamos')}
config['services']['nginx']['ports'] = [{'target':80,'published':'18080','host_ip':'127.0.0.1','protocol':'tcp'}]
config['services']['svc-prestamos']['volumes'] = [{'type':'bind','source':str(ROOT/'tests'),'target':'/integration','read_only':True}]
# The project name is fixed here to prevent accidental use of production volume names.
config['name'] = 'biblioteca-verificacion'
config['networks'] = {'default': {}}
config['volumes'] = {key:{} for key in config['volumes'] if key not in ('mysql_data','mysql_auth')}
output = Path('/tmp/biblioteca-integration-compose.json')
fd=os.open(str(output),os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
with os.fdopen(fd,'w') as f:
    json.dump(config,f)
print(output)
