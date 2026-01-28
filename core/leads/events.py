from __future__ import annotations

from typing import Any
from core.leads.models import Lead, LeadEvent


def record_lead_event(
    *,
    lead: Lead,
    event_type: str,
    source: str,
    actor_user_id=None,
    data: dict[str, Any] | None = None,
) -> LeadEvent:
    """
    Always tenant-safe: tenant derived from lead.
    """
    return LeadEvent.objects.create(
        tenant=lead.tenant,
        lead=lead,
        type=event_type,
        source=source,
        actor_user_id=actor_user_id,
        data_json=data or {},
    )
