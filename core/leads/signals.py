from __future__ import annotations

from django.db.models.signals import post_save
from django.dispatch import receiver

from core.conversations.models import Message
from core.leads.tasks import enrich_conversation_signals


@receiver(post_save, sender=Message)
def on_message_saved(sender, instance: Message, created: bool, **kwargs):
    # Only on new user messages (signals come from user text)
    if not created:
        return
    if instance.role != Message.Role.USER:
        return

    # Fire-and-forget async task
    enrich_conversation_signals.delay(str(instance.tenant_id), str(instance.conversation_id))
