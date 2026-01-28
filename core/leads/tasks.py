from __future__ import annotations

from celery import shared_task
from django.db import transaction
from django.utils import timezone

from core.common.flags import is_enabled
from core.conversations.models import Conversation, Message
from core.leads.models import Lead
from core.leads.enrichment import build_signals_from_messages


@shared_task(bind=True, max_retries=3, default_retry_delay=5)
def enrich_conversation_signals(self, tenant_id: str, conversation_id: str) -> None:
    """
    Recomputes signals from recent conversation messages and stores into:
      - Conversation.meta_json["signals"]
      - Lead.meta_json["signals"] (if a lead is linked to the conversation)

    Runs only if lead_enrichment_enabled flag is ON for this tenant.
    """
    if not is_enabled(str(tenant_id), "lead_enrichment_enabled"):
        return

    convo = Conversation.objects.filter(id=conversation_id, tenant_id=tenant_id).first()
    if not convo:
        return

    # Pull recent user messages (more signal, less noise)
    msgs = (
        Message.objects.filter(tenant_id=tenant_id, conversation_id=conversation_id, role=Message.Role.USER)
        .order_by("-created_at")[:50]
    )
    msg_texts = [m.content for m in reversed(list(msgs))]

    snapshot = build_signals_from_messages(msg_texts)
    snapshot_dict = {
        "topics": snapshot.topics,
        "intents": snapshot.intents,
        "sentiment": snapshot.sentiment,
        "score": snapshot.score,
        "updated_at": snapshot.updated_at,
        "source": "rules_v1",
    }

    with transaction.atomic():
        convo = Conversation.objects.select_for_update().get(id=conversation_id, tenant_id=tenant_id)
        meta = convo.meta_json or {}
        meta["signals"] = snapshot_dict
        convo.meta_json = meta
        convo.updated_at = timezone.now()
        convo.save(update_fields=["meta_json", "updated_at"])

        # If lead exists for this conversation, copy signals into lead meta_json too
        lead = (
            Lead.objects.select_for_update()
            .filter(tenant_id=tenant_id, conversation_id=conversation_id, deleted_at__isnull=True)
            .order_by("created_at")
            .first()
        )
        if lead:
            lmeta = lead.meta_json or {}
            lmeta["signals"] = snapshot_dict
            lead.meta_json = lmeta
            lead.updated_at = timezone.now()
            lead.save(update_fields=["meta_json", "updated_at"])
