"""At-least-once transport. Domain writes, inbox and outbox use each service's DB."""
import importlib
import json
import logging
import time
import uuid
from datetime import timedelta
from django.apps import apps
from django.conf import settings
from django.db import transaction, close_old_connections
from django.utils import timezone

log = logging.getLogger(__name__)
EXCHANGE = 'biblioteca.v1'


def model(name):
    return apps.get_model(settings.SERVICE_NAME, name)


def emit(target, kind, saga_id, payload):
    mid = uuid.uuid4()
    body = dict(message_id=str(mid), saga_id=str(saga_id), version=1, type=kind, payload=payload)
    return model('Outbox').objects.create(id=mid, routing_key=target+'.'+kind, body=body)


def validate(message):
    uuid.UUID(message['message_id'])
    uuid.UUID(message['saga_id'])
    if message['version'] != 1 or not isinstance(message['payload'],dict):
        raise ValueError('Mensaje incompatible.')
    for key in ('prestamo_id','libro_id'):
        value = message['payload'][key]
        if type(value) is not int or not 0 < value <= 9223372036854775807:
            raise ValueError('Referencia de 64 bits inválida: '+key)


@transaction.atomic
def process(message):
    validate(message)
    _, created = model('Inbox').objects.get_or_create(message_id=message['message_id'])
    if not created:
        return False
    importlib.import_module(settings.SERVICE_NAME+'.domain').handle(message)
    log.info('processed saga_id=%s message_id=%s type=%s', message['saga_id'], message['message_id'],message['type'])
    return True


def topology(channel):
    channel.exchange_declare(exchange=EXCHANGE, exchange_type='topic', durable=True)
    for service in ('catalogo','circulacion'):
        channel.queue_declare(queue=service, durable=True)
        channel.queue_bind(queue=service, exchange=EXCHANGE, routing_key=service+'.*')
        channel.queue_declare(queue=service+'.failed', durable=True)
        # TTL queues preserve retries across crashes, without sleeping in callbacks.
        for attempt in range(1,6):
            channel.queue_declare(queue=f'{service}.retry.{attempt}', durable=True, arguments={
                'x-message-ttl': min(2**attempt,30)*1000,
                'x-dead-letter-exchange':'', 'x-dead-letter-routing-key':service})
    channel.confirm_delivery()


def publish(channel, key, body, headers=None, exchange=EXCHANGE):
    import pika
    channel.basic_publish(exchange=exchange, routing_key=key, body=json.dumps(body).encode(), mandatory=True,
        properties=pika.BasicProperties(delivery_mode=2, content_type='application/json',
                                       message_id=body.get('message_id'), headers=headers or {}))


def flush(channel):
    # Lock through confirm, then mark published. A crash can duplicate, never silently lose.
    ids = list(model('Outbox').objects.filter(published_at__isnull=True, next_attempt_at__lte=timezone.now())
               .order_by('created_at').values_list('pk',flat=True)[:100])
    for mid in ids:
        with transaction.atomic():
            row = model('Outbox').objects.select_for_update().get(pk=mid)
            if row.published_at:
                continue
            try:
                publish(channel, row.routing_key, row.body)
            except Exception as exc:
                row.attempts += 1
                row.last_error = str(exc)[:1000]
                row.next_attempt_at = timezone.now()+timedelta(seconds=min(2**min(row.attempts,8),60))
                row.save()
                log.exception('publish pending saga_id=%s', row.body['saga_id'])
                return
            row.published_at = timezone.now()
            row.last_error = ''
            row.save(update_fields=['published_at','last_error'])


def failed_id(body):
    try:
        return uuid.UUID(str(body['message_id']))
    except (KeyError,ValueError,TypeError):
        return uuid.uuid5(uuid.NAMESPACE_OID, json.dumps(body,sort_keys=True))


def consume(channel, method, properties, raw):
    body = None
    try:
        body = json.loads(raw)
        process(body)
    except Exception as exc:
        attempts = (properties.headers or {}).get('attempt',0) + 1
        if not isinstance(body,dict):
            body = {'raw':raw.decode(errors='replace')}
        try:
            if attempts <= 5:
                publish(channel, f'{settings.SERVICE_NAME}.retry.{attempts}', body, {'attempt':attempts}, exchange='')
            else:
                model('FailedMessage').objects.update_or_create(message_id=failed_id(body),
                    defaults={'body':body, 'error':str(exc)[:4000], 'replayed_at':None})
                publish(channel, settings.SERVICE_NAME+'.failed', body, {'error':str(exc)[:1000]}, exchange='')
                log.exception('dead letter saga_id=%s',body.get('saga_id'))
        except Exception:
            channel.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
            raise
    channel.basic_ack(delivery_tag=method.delivery_tag)


def run():
    import pika
    while True:
        connection = None
        try:
            close_old_connections()
            params = pika.URLParameters(settings.RABBITMQ_URL)
            params.heartbeat = 60
            params.blocked_connection_timeout = 10
            params.socket_timeout = 5
            connection = pika.BlockingConnection(params)
            channel = connection.channel()
            topology(channel)
            channel.basic_qos(prefetch_count=1)
            last_recovery = time.monotonic()
            for method, properties, body in channel.consume(settings.SERVICE_NAME, inactivity_timeout=1, auto_ack=False):
                if method:
                    consume(channel,method,properties,body)
                flush(channel)
                if settings.SERVICE_NAME=='circulacion' and time.monotonic()-last_recovery>30:
                    importlib.import_module('circulacion.domain').recover(timezone.now()-timedelta(seconds=60))
                    last_recovery=time.monotonic()
        except KeyboardInterrupt:
            return
        except Exception:
            log.exception('Worker reconnecting')
            time.sleep(3)
        finally:
            if connection and connection.is_open:
                connection.close()
