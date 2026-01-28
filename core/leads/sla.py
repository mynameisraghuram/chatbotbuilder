from __future__ import annotations

from datetime import timedelta
from django.utils import timezone

from core.leads.models import Lead, LeadSlaPolicy


DEFAULT_MINUTES_BY_STATUS = {
    "new": 60,
    "open": 240,
    "qualified": 1440,  # 1 day
    "closed": 0,        # no reminders by default
}


def get_policy_for_tenant(tenant_id):
    return (
        LeadSlaPolicy.objects.filter(tenant_id=tenant_id, is_enabled=True)
        .order_by("-updated_at")
        .first()
    )


def compute_next_action_at(*, lead: Lead, policy: LeadSlaPolicy | None):
    """
    Returns a datetime or None.
    - Normalizes lead.status to lowercase
    - Merges default map + policy map (policy wins)
    - If minutes <= 0 => None (disabled)
    """
    mins_map = dict(DEFAULT_MINUTES_BY_STATUS)

    if policy and isinstance(policy.minutes_by_status, dict):
        for k, v in policy.minutes_by_status.items():
            if k is None:
                continue
            try:
                mins_map[str(k).strip().lower()] = int(v)
            except Exception:
                continue

    status_key = (lead.status or "new")
    status_key = str(status_key).strip().lower()

    mins = mins_map.get(status_key)

    # If no SLA configured for this status, do not schedule.
    if mins is None:
        return None

    # minutes <= 0 disables reminders
    if int(mins) <= 0:
        return None

    base = lead.last_contacted_at or lead.created_at or timezone.now()
    return base + timedelta(minutes=int(mins))


def truncate_to_minute(dt):
    if not dt:
        return None
    return dt.replace(second=0, microsecond=0)
