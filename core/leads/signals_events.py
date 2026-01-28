from __future__ import annotations

from django.db.models.signals import post_save
from django.dispatch import receiver

from core.leads.models import Lead
from core.leads.events import record_lead_event


@receiver(post_save, sender=Lead)
def on_lead_created(sender, instance: Lead, created: bool, **kwargs):
    if not created:
        return
    if instance.deleted_at is not None:
        return

    record_lead_event(
        lead=instance,
        event_type="lead.created",
        source="system",
        actor_user_id=None,
        data={
            "name": instance.name or "",
            "email": instance.primary_email or "",
            "phone": instance.phone or "",
            "conversation_id": str(instance.conversation_id) if instance.conversation_id else None,
            "chatbot_id": str(instance.chatbot_id) if instance.chatbot_id else None,
        },
    )
