import uuid
from django.db import models
from django.utils import timezone

from core.tenants.models import Tenant


class Chatbot(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        DISABLED = "disabled", "Disabled"

    class Tone(models.TextChoices):
        FRIENDLY = "friendly", "Friendly"
        PROFESSIONAL = "professional", "Professional"
        SUPPORT = "support", "Support"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="chatbots")

    name = models.CharField(max_length=120)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE)
    tone = models.CharField(max_length=16, choices=Tone.choices, default=Tone.FRIENDLY)

    branding_json = models.JSONField(default=dict, blank=True)
    lead_capture_enabled = models.BooleanField(default=False)
    citations_enabled = models.BooleanField(default=False)

    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["tenant", "status"]),
            models.Index(fields=["tenant", "deleted_at"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "name"],
                name="uq_chatbot_tenant_name",
                condition=models.Q(deleted_at__isnull=True),
            )
        ]

    def soft_delete(self):
        if not self.deleted_at:
            self.deleted_at = timezone.now()
            self.status = self.Status.DISABLED
            self.save(update_fields=["deleted_at", "status", "updated_at"])
