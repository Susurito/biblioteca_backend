import uuid
from django.db import models
from django.utils import timezone

class Outbox(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    routing_key = models.CharField(max_length=100)
    body = models.JSONField()
    created_at = models.DateTimeField(default=timezone.now)
    published_at = models.DateTimeField(null=True)
    attempts = models.PositiveIntegerField(default=0)
    next_attempt_at = models.DateTimeField(default=timezone.now)
    last_error = models.TextField(blank=True)

class Inbox(models.Model):
    message_id = models.UUIDField(primary_key=True)
    processed_at = models.DateTimeField(default=timezone.now)

class FailedMessage(models.Model):
    message_id = models.UUIDField(primary_key=True)
    body = models.JSONField()
    error = models.TextField()
    failed_at = models.DateTimeField(default=timezone.now)
    replayed_at = models.DateTimeField(null=True)
