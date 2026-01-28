import json
import urllib.request
import urllib.error

from celery import shared_task
from django.utils import timezone
from datetime import timedelta

from core.webhooks.models import WebhookDelivery


def _backoff_minutes(attempts: int) -> int:
    # attempts starts at 0; first retry -> 1 minute
    schedule = [1, 5, 15, 60, 180, 720]  # up to 12h
    idx = min(max(attempts, 0), len(schedule) - 1)
    return schedule[idx]


@shared_task(bind=True, max_retries=0)
def deliver_webhook_delivery(self, delivery_id: str):
    d = WebhookDelivery.objects.select_related("endpoint").filter(id=delivery_id).first()
    if not d:
        return

    if d.status in (WebhookDelivery.STATUS_SENT, WebhookDelivery.STATUS_FAILED):
        return

    if d.next_attempt_at and d.next_attempt_at > timezone.now():
        return

    ep = d.endpoint
    if not ep.is_active or ep.tenant_id != d.tenant_id:
        d.status = WebhookDelivery.STATUS_FAILED
        d.last_error = "Endpoint inactive or tenant mismatch"
        d.touch()
        d.save(update_fields=["status", "last_error", "updated_at"])
        return

    payload = {
        "type": d.event_type,
        "tenant_id": str(d.tenant_id),
        "data": d.payload_json,
        "delivery_id": str(d.id),
        "created_at": d.created_at.isoformat(),
    }
    body = json.dumps(payload).encode("utf-8")

    signature = WebhookDelivery.sign_payload(ep.secret, payload)

    req = urllib.request.Request(
        ep.url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "X-Webhook-Signature": signature,
            "X-Webhook-Event": d.event_type,
        },
        method="POST",
    )

    d.attempts += 1
    d.touch()
    d.save(update_fields=["attempts", "updated_at"])

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            status = int(getattr(resp, "status", 200))
            if 200 <= status < 300:
                d.status = WebhookDelivery.STATUS_SENT
                d.delivered_at = timezone.now()
                d.last_http_status = status
                d.last_error = None
                d.next_attempt_at = None
                d.save(update_fields=["status", "delivered_at", "last_http_status", "last_error", "next_attempt_at"])
                return

            # treat non-2xx as failure (retry on 5xx/429)
            d.last_http_status = status
            raise urllib.error.HTTPError(ep.url, status, "non-2xx", hdrs=None, fp=None)

    except urllib.error.HTTPError as e:
        status = int(getattr(e, "code", 0) or 0)
        d.last_http_status = status
        d.last_error = f"HTTPError {status}"
        retryable = (status == 429) or (500 <= status <= 599)

    except Exception as e:
        d.last_error = f"Exception: {type(e).__name__}: {e}"
        retryable = True

    if d.attempts >= 6 or not retryable:
        d.status = WebhookDelivery.STATUS_FAILED
        d.next_attempt_at = None
        d.save(update_fields=["status", "last_http_status", "last_error", "next_attempt_at"])
        return

    mins = _backoff_minutes(d.attempts)
    d.next_attempt_at = timezone.now() + timedelta(minutes=mins)
    d.save(update_fields=["last_http_status", "last_error", "next_attempt_at"])
