import uuid
import hmac
import hashlib
import json

from django.db import models
from django.utils import timezone


class WebhookEndpoint(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    tenant_id = models.UUIDField(db_index=True)

    url = models.URLField(max_length=1000)
    secret = models.CharField(max_length=200)  # store random secret per endpoint
    is_active = models.BooleanField(default=True, db_index=True)

    # optional: which events this endpoint wants; empty => receive all
    events_json = models.JSONField(default=list, blank=True)

    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    updated_at = models.DateTimeField(default=timezone.now)

    def touch(self):
        self.updated_at = timezone.now()
        self.save(update_fields=["updated_at"])

    def allows(self, event_type: str) -> bool:
        events = self.events_json or []
        if not events:
            return True
        return event_type in set(str(x) for x in events)

    def __str__(self):
        return f"WebhookEndpoint({self.tenant_id}, {self.url})"


class WebhookDelivery(models.Model):
    STATUS_PENDING = "pending"
    STATUS_SENT = "sent"
    STATUS_FAILED = "failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    tenant_id = models.UUIDField(db_index=True)
    endpoint = models.ForeignKey(WebhookEndpoint, on_delete=models.CASCADE, related_name="deliveries")

    event_type = models.CharField(max_length=100, db_index=True)
    payload_json = models.JSONField(default=dict)

    status = models.CharField(
        max_length=20,
        default=STATUS_PENDING,
        choices=[
            (STATUS_PENDING, "Pending"),
            (STATUS_SENT, "Sent"),
            (STATUS_FAILED, "Failed"),
        ],
        db_index=True,
    )

    attempts = models.IntegerField(default=0)
    next_attempt_at = models.DateTimeField(null=True, blank=True, db_index=True)

    last_http_status = models.IntegerField(null=True, blank=True)
    last_error = models.TextField(null=True, blank=True)

    delivered_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    updated_at = models.DateTimeField(default=timezone.now)

    def touch(self):
        self.updated_at = timezone.now()
        self.save(update_fields=["updated_at"])

    @staticmethod
    def sign_payload(secret: str, payload: dict) -> str:
        raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
        sig = hmac.new(secret.encode("utf-8"), raw, hashlib.sha256).hexdigest()
        return sig
