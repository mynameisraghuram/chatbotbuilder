import uuid
from django.db import models
from django.utils import timezone

from core.tenants.models import Tenant
from core.chatbots.models import Chatbot


class Conversation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="conversations")
    chatbot = models.ForeignKey(Chatbot, on_delete=models.CASCADE, related_name="conversations")
    lead = models.ForeignKey(
    "leads.Lead",
    null=True,
    blank=True,
    on_delete=models.SET_NULL,
    related_name="conversations",
)


    # Public identity (browser/user)
    external_user_id = models.CharField(max_length=128, blank=True, default="")
    session_id = models.CharField(max_length=128, blank=True, default="")
    user_email = models.EmailField(blank=True, default="")

    # Light metadata (no PII explosion)
    meta_json = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["tenant", "created_at"]),
            models.Index(fields=["tenant", "chatbot", "created_at"]),
            models.Index(fields=["chatbot", "created_at"]),
        ]


class Message(models.Model):
    class Role(models.TextChoices):
        USER = "user", "User"
        ASSISTANT = "assistant", "Assistant"
        SYSTEM = "system", "System"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="messages")
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="messages")

    role = models.CharField(max_length=16, choices=Role.choices)
    content = models.TextField()

    # future: citations, retrieval debug, etc.
    meta_json = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        indexes = [
            models.Index(fields=["tenant", "conversation", "created_at"]),
            models.Index(fields=["conversation", "created_at"]),
        ]
