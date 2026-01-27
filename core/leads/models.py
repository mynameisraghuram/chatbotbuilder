import uuid
from django.db import models
from django.utils import timezone


class Lead(models.Model):
    class Status(models.TextChoices):
        NEW = "new", "New"
        OPEN = "open", "Open"
        QUALIFIED = "qualified", "Qualified"
        CLOSED = "closed", "Closed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    tenant = models.ForeignKey("tenants.Tenant", on_delete=models.CASCADE, related_name="leads")
    chatbot = models.ForeignKey("chatbots.Chatbot", on_delete=models.CASCADE, related_name="leads")
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
