from __future__ import annotations

from django.db import transaction
from django.utils import timezone
from celery import shared_task

from core.common.flags import is_enabled
from core.leads.models import Lead, LeadReminder
from core.leads.sla import get_policy_for_tenant, compute_next_action_at, truncate_to_minute
from core.leads.events import record_lead_event


@shared_task
def schedule_lead_reminders():
    """
    Runs periodically (every 5 minutes).
    Finds leads with next_action_at <= now and schedules reminder rows (deduped).
    """
    now = timezone.now()

    # NOTE: multi-tenant scan. OK for MVP scale; later optimize with per-tenant batching.
    qs = Lead.objects.filter(
        deleted_at__isnull=True,
        next_action_at__isnull=False,
        next_action_at__lte=now,
    ).only("id", "tenant_id", "status", "next_action_at", "last_contacted_at", "created_at")

    for lead in qs.iterator(chunk_size=500):
        # Tenant gating
        if not is_enabled(str(lead.tenant_id), "crm_enabled"):
            continue
        if not is_enabled(str(lead.tenant_id), "lead_sla_enabled"):
            continue

        policy = get_policy_for_tenant(lead.tenant_id)
        scheduled_for = truncate_to_minute(lead.next_action_at) or truncate_to_minute(now)
        if not scheduled_for:
            continue

        try:
            with transaction.atomic():
                # re-lock lead to avoid races
                locked = Lead.objects.select_for_update().get(id=lead.id, tenant_id=lead.tenant_id, deleted_at__isnull=True)

                # re-check time after lock
                if not locked.next_action_at or locked.next_action_at > timezone.now():
                    continue

                # create reminder row (deduped by unique constraint)
                rem, created = LeadReminder.objects.get_or_create(
                    tenant_id=locked.tenant_id,
                    lead_id=locked.id,
                    reason="sla",
                    scheduled_for=scheduled_for,
                    defaults={"status": LeadReminder.Status.SCHEDULED},
                )

                if created:
                    record_lead_event(
                        lead=locked,
                        event_type="lead.reminder.scheduled",
                        source="system",
                        actor_user_id=None,
                        data={"scheduled_for": scheduled_for.isoformat(), "reason": "sla"},
                    )

                # enqueue delivery
                deliver_lead_reminder.delay(int(rem.id))
        except Exception:
            # scheduler should be robust; swallow per-lead failures
            continue


@shared_task(bind=True, max_retries=3, default_retry_delay=10)
def deliver_lead_reminder(self, reminder_id: int):
    """
    Delivery stub: mark reminder SENT and record event.
    Later: send email/webhook to assigned owner/admins.
    """
    now = timezone.now()
    rem = LeadReminder.objects.select_related("lead").filter(id=reminder_id).first()
    if not rem:
        return
    if rem.status != LeadReminder.Status.SCHEDULED:
        return

    lead = rem.lead
    if not is_enabled(str(rem.tenant_id), "crm_enabled") or not is_enabled(str(rem.tenant_id), "lead_sla_enabled"):
        # cancel if feature off
        rem.status = LeadReminder.Status.CANCELED
        rem.updated_at = now
        rem.save(update_fields=["status", "updated_at"])
        return

    try:
        with transaction.atomic():
            rem = LeadReminder.objects.select_for_update().select_related("lead").get(id=reminder_id)
            if rem.status != LeadReminder.Status.SCHEDULED:
                return

            # TODO: Integrate email/webhook. For now just mark sent.
            rem.status = LeadReminder.Status.SENT
            rem.sent_at = now
            rem.updated_at = now
            rem.save(update_fields=["status", "sent_at", "updated_at"])

            record_lead_event(
                lead=rem.lead,
                event_type="lead.reminder.sent",
                source="system",
                actor_user_id=None,
                data={"scheduled_for": rem.scheduled_for.isoformat(), "sent_at": now.isoformat()},
            )
    except Exception as e:
        rem.attempts += 1
        rem.last_error = str(e)[:2000]
        rem.updated_at = now
        if rem.attempts >= 3:
            rem.status = LeadReminder.Status.FAILED
        rem.save(update_fields=["attempts", "last_error", "status", "updated_at"])
        raise
