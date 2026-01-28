import uuid
from django.db import models
from django.utils import timezone


class ApiKey(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        REVOKED = "revoked", "Revoked"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    tenant = models.ForeignKey("tenants.Tenant", on_delete=models.CASCADE, related_name="api_keys")
    chatbot = models.ForeignKey("chatbots.Chatbot", on_delete=models.CASCADE, related_name="api_keys")

    key_hash = models.CharField(max_length=64, unique=True, db_index=True)
    key_prefix = models.CharField(max_length=16, blank=True, default="", db_index=True)

    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE)
    rate_limit_per_min = models.PositiveIntegerField(default=60)

    last_used_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        db_table = "api_keys"
        indexes = [
            models.Index(fields=["tenant", "chatbot", "created_at"]),
            models.Index(fields=["tenant", "chatbot", "status"]),
            models.Index(fields=["key_prefix"]),
        ]

    def revoke(self):
        if self.status != self.Status.REVOKED:
            self.status = self.Status.REVOKED
            self.revoked_at = timezone.now()
            self.save(update_fields=["status", "revoked_at"])

    def mark_used(self):
        self.last_used_at = timezone.now()
        self.save(update_fields=["last_used_at"])
