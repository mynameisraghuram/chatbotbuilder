from datetime import timedelta
from celery import shared_task
from django.contrib.auth import get_user_model
from django.utils import timezone

from django.db import models


from core.common.flags import is_enabled
from core.webhooks.emailing import send_simple_email
from core.iam.models import TenantMembership
from core.leads.models import LeadReminder
from core.leads.events import record_lead_event
from core.webhooks.models import WebhookEndpoint, WebhookDelivery
from core.webhooks.tasks import deliver_webhook_delivery

User = get_user_model()


def _backoff_minutes(attempts: int) -> int:
    schedule = [1, 5, 15, 60, 180, 720]  # up to 12h
    idx = min(max(attempts, 0), len(schedule) - 1)
    return schedule[idx]


def _recipient_user_ids_for_lead(tenant_id, lead) -> list:
    assignee = getattr(lead, "assigned_to_user_id", None)
    if assignee:
        return [assignee]
    qs = TenantMembership.objects.filter(
        tenant_id=tenant_id,
        role__in=[TenantMembership.ROLE_OWNER, TenantMembership.ROLE_ADMIN],
    ).values_list("user_id", flat=True)
    return list(qs)


@shared_task
def process_due_lead_reminders():
    now = timezone.now()

    qs = LeadReminder.objects.select_related("lead").filter(
        status=LeadReminder.Status.SCHEDULED,
    ).filter(
        models.Q(next_attempt_at__isnull=True) | models.Q(next_attempt_at__lte=now)
    ).order_by("created_at")[:200]

    for r in qs:
        deliver_lead_reminder.delay(int(r.id))


@shared_task(bind=True, max_retries=0)
def deliver_lead_reminder(self, reminder_id: int):
    r = LeadReminder.objects.select_related("lead").filter(id=reminder_id).first()
    if not r:
        return

    if r.status in (LeadReminder.Status.SENT, LeadReminder.Status.FAILED, LeadReminder.Status.CANCELED):
        return

    if r.next_attempt_at and r.next_attempt_at > timezone.now():
        return

    lead = r.lead
    tenant_id = r.tenant_id

    if not is_enabled(str(tenant_id), "crm_enabled") or not is_enabled(str(tenant_id), "lead_sla_enabled"):
        r.status = LeadReminder.Status.FAILED
        r.last_error = "Feature disabled"
        r.save(update_fields=["status", "last_error"])
        return

    user_ids = _recipient_user_ids_for_lead(tenant_id, lead)
    users = list(User.objects.filter(id__in=user_ids))

    any_sent = False
    last_err = None

    # EMAIL
    for u in users:
        email = (getattr(u, "email", "") or "").strip()
        if not email:
            continue
        try:
            subject = "Lead follow-up reminder"
            body = (
                f"Reminder to follow up on lead:\n\n"
                f"Name: {getattr(lead, 'name', '')}\n"
                f"Email: {getattr(lead, 'primary_email', '')}\n"
                f"Phone: {getattr(lead, 'phone', '')}\n"
                f"Status: {getattr(lead, 'status', '')}\n"
            )
            send_simple_email(subject=subject, body=body, to_email=email)
            any_sent = True
        except Exception as e:
            last_err = f"email error: {type(e).__name__}: {e}"

    # WEBHOOKS (async per endpoint)
    if is_enabled(str(tenant_id), "webhooks_enabled"):
        endpoints = WebhookEndpoint.objects.filter(tenant_id=tenant_id, is_active=True)
        payload = {
            "lead_id": str(lead.id),
            "reminder_id": str(r.id),
            "assigned_to_user_id": str(lead.assigned_to_user_id) if getattr(lead, "assigned_to_user_id", None) else None,
            "scheduled_for": r.scheduled_for.isoformat(),
        }
        for ep in endpoints:
            if not ep.allows("lead.reminder.due"):
                continue
            d = WebhookDelivery.objects.create(
                tenant_id=tenant_id,
                endpoint=ep,
                event_type="lead.reminder.due",
                payload_json=payload,
                status=WebhookDelivery.STATUS_PENDING,
            )
            deliver_webhook_delivery.delay(str(d.id))

    # finalize reminder
    r.attempts = int(r.attempts or 0) + 1

    if any_sent:
        r.status = LeadReminder.Status.SENT
        r.sent_at = timezone.now()
        r.last_error = None
        r.last_channel = "email"
        r.next_attempt_at = None
        r.save(update_fields=["status", "attempts", "sent_at", "last_error", "last_channel", "next_attempt_at"])

        record_lead_event(
            lead=lead,
            event_type="lead.reminder.sent",
            source="system",
            actor_user_id=None,
            data={"reminder_id": str(r.id), "channels": ["email"]},
        )
        return

    if r.attempts >= 6:
        r.status = LeadReminder.Status.FAILED
        r.last_error = last_err or "No recipients with email"
        r.next_attempt_at = None
        r.save(update_fields=["status", "attempts", "last_error", "next_attempt_at"])

        record_lead_event(
            lead=lead,
            event_type="lead.reminder.failed",
            source="system",
            actor_user_id=None,
            data={"reminder_id": str(r.id), "error": r.last_error},
        )
        return

    mins = _backoff_minutes(r.attempts)
    r.last_error = last_err or "No recipients with email"
    r.next_attempt_at = timezone.now() + timedelta(minutes=mins)
    r.save(update_fields=["attempts", "last_error", "next_attempt_at"])
