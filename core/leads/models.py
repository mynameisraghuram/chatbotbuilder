import uuid
from django.db import models
from django.utils import timezone

import hashlib
from django.conf import settings

class Lead(models.Model):
    class Status(models.TextChoices):
        NEW = "new", "New"
        OPEN = "open", "Open"
        QUALIFIED = "qualified", "Qualified"
        CLOSED = "closed", "Closed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    tenant = models.ForeignKey("tenants.Tenant", on_delete=models.CASCADE, related_name="leads")
    chatbot = models.ForeignKey("chatbots.Chatbot", on_delete=models.SET_NULL, null=True, blank=True, related_name="leads")

    conversation = models.ForeignKey(
        "conversations.Conversation",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="leads",
    )

    name = models.CharField(max_length=200, blank=True, default="")
    primary_email = models.EmailField(blank=True, default="")
    phone = models.CharField(max_length=32, blank=True, default="")

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NEW)

    email_verified = models.BooleanField(default=False)
    verified_at = models.DateTimeField(null=True, blank=True)

    meta_json = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    updated_at = models.DateTimeField(default=timezone.now, db_index=True)
    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        db_table = "leads"
        indexes = [
            models.Index(fields=["tenant", "created_at"]),
            models.Index(fields=["tenant", "chatbot", "created_at"]),
            models.Index(fields=["tenant", "primary_email"]),
            models.Index(fields=["tenant", "phone"]),
        ]

    def soft_delete(self):
        if not self.deleted_at:
            self.deleted_at = timezone.now()
            self.save(update_fields=["deleted_at", "updated_at"])

    def touch(self):
        self.updated_at = timezone.now()
        self.save(update_fields=["updated_at"])

class LeadEvent(models.Model):
    """
    Immutable-ish event stream for a Lead.
    Avoid updates; create new events instead.
    """

    class Source(models.TextChoices):
        SYSTEM = "system", "System"
        PUBLIC = "public", "Public"
        DASHBOARD = "dashboard", "Dashboard"

    id = models.BigAutoField(primary_key=True)

    tenant = models.ForeignKey("tenants.Tenant", on_delete=models.CASCADE, related_name="lead_events")
    lead = models.ForeignKey("leads.Lead", on_delete=models.CASCADE, related_name="events")

    # who caused it (null for public/system)
    actor_user_id = models.UUIDField(null=True, blank=True, db_index=True)

    # machine-readable type
    type = models.CharField(max_length=64, db_index=True)

    source = models.CharField(max_length=16, choices=Source.choices, default=Source.SYSTEM)

    # flexible payload; do not store raw secrets
    data_json = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        db_table = "lead_events"
        indexes = [
            models.Index(fields=["tenant", "lead", "created_at"]),
            models.Index(fields=["tenant", "type", "created_at"]),
        ]



class LeadNote(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    tenant = models.ForeignKey("tenants.Tenant", on_delete=models.CASCADE, related_name="lead_notes")
    lead = models.ForeignKey("leads.Lead", on_delete=models.CASCADE, related_name="notes")

    body = models.TextField()

    created_by_user_id = models.UUIDField(db_index=True)
    updated_by_user_id = models.UUIDField(null=True, blank=True, db_index=True)

    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    updated_at = models.DateTimeField(default=timezone.now, db_index=True)

    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        db_table = "lead_notes"
        indexes = [
            models.Index(fields=["tenant", "lead", "created_at"]),
            models.Index(fields=["tenant", "lead", "deleted_at"]),
        ]

    def soft_delete(self):
        now = timezone.now()
        self.deleted_at = now
        self.updated_at = now
        self.save(update_fields=["deleted_at", "updated_at"])

class OtpVerification(models.Model):
    """
    Stores hashed OTP only (never plaintext).
    Used for verifying lead email via public widget flow.
    """
    id = models.BigAutoField(primary_key=True)

    tenant = models.ForeignKey("tenants.Tenant", on_delete=models.CASCADE, related_name="otp_verifications")
    lead = models.ForeignKey("leads.Lead", on_delete=models.CASCADE, related_name="otp_verifications")

    email = models.EmailField(db_index=True)
    otp_hash = models.CharField(max_length=64)

    expires_at = models.DateTimeField(db_index=True)
    attempt_count = models.PositiveIntegerField(default=0)

    verified_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        db_table = "otp_verifications"
        indexes = [
            models.Index(fields=["tenant", "lead", "created_at"]),
            models.Index(fields=["tenant", "email", "expires_at"]),
        ]

    @staticmethod
    def hash_otp(email: str, otp: str) -> str:
        salt = getattr(settings, "SECRET_KEY", "dev")
        payload = f"{email.strip().lower()}|{otp}|{salt}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


