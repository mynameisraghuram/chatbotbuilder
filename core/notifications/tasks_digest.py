from datetime import timedelta

from celery import shared_task
from django.contrib.auth import get_user_model
from django.utils import timezone

from core.common.emailing import send_simple_email
from core.notifications.models import NotificationPreference, NotificationEvent


User = get_user_model()


def _is_weekly_run(now, mode: str) -> bool:
    # weekly digest: pick Monday (0)
    if mode != NotificationPreference.DigestMode.WEEKLY:
        return True
    return now.weekday() == 0


def _digest_window(now, mode: str):
    if mode == NotificationPreference.DigestMode.DAILY:
        return now - timedelta(days=1)
    if mode == NotificationPreference.DigestMode.WEEKLY:
        return now - timedelta(days=7)
    return None


def _format_digest(events):
    # Keep it simple, stable, and human-readable
    lines = []
    for e in events:
        t = e.type
        payload = e.payload_json or {}
        lead_name = payload.get("lead_name") or ""
        lead_id = payload.get("lead_id") or ""
        when = e.created_at.isoformat(timespec="minutes")
        lines.append(f"- [{when}] {t} lead={lead_name} ({lead_id})")
    return "\n".join(lines) if lines else "No updates."


@shared_task
def send_due_notification_digests():
    """
    Runs hourly (or more). Sends digest emails based on digest_hour and mode.
    Marks included events as digested_at.
    """
    now = timezone.now()
    hour = now.hour

    # Only users with digest enabled and matching hour
    prefs = NotificationPreference.objects.filter(
        digest_mode__in=[
            NotificationPreference.DigestMode.DAILY,
            NotificationPreference.DigestMode.WEEKLY,
        ],
        digest_hour=hour,
    ).order_by("tenant_id", "user_id")[:2000]  # safety cap

    for p in prefs:
        if not _is_weekly_run(now, p.digest_mode):
            continue

        user = User.objects.filter(id=p.user_id).first()
        if not user:
            continue

        email = (getattr(user, "email", "") or "").strip()
        if not email:
            continue

        since = _digest_window(now, p.digest_mode)
        if not since:
            continue

        # Pull undigested events in the window
        qs = NotificationEvent.objects.filter(
            tenant_id=p.tenant_id,
            user_id=p.user_id,
            digested_at__isnull=True,
            created_at__gte=since,
        ).order_by("created_at")[:200]  # cap per digest

        events = list(qs)
        if not events:
            # don't spam empty digests
            continue

        subject = "Your activity digest"
        body = _format_digest(events)

        try:
            send_simple_email(subject=subject, body=body, to_email=email)
        except Exception:
            # If email fails, keep events undigested for next run
            continue

        # Mark all as digested
        ids = [e.id for e in events]
        NotificationEvent.objects.filter(id__in=ids).update(digested_at=timezone.now())
