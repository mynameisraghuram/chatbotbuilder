import secrets
import pytest
from rest_framework.test import APIClient

from core.tenants.models import Tenant
from core.chatbots.models import Chatbot
from core.api_keys.models import ApiKey
from core.api_keys.utils import hash_key
from core.leads.models import Lead


@pytest.mark.django_db
def test_public_lead_capture_smoke_no_tenant_header_required():
    tenant = Tenant.objects.create(name="Acme")

    bot = Chatbot.objects.create(
        tenant=tenant,
        name="Acme Bot",
        status=Chatbot.Status.ACTIVE,
        citations_enabled=True,
        lead_capture_enabled=True,
    )

    raw_key = "cb_live_" + secrets.token_urlsafe(24)

    fields = {f.name for f in ApiKey._meta.get_fields()}
    create_kwargs = {
        "tenant": tenant,
        "chatbot": bot,
        "key_hash": hash_key(raw_key),
    }
    if "status" in fields:
        create_kwargs["status"] = ApiKey.Status.ACTIVE
    if "rate_limit_per_min" in fields:
        create_kwargs["rate_limit_per_min"] = 60
    elif "rate_limit" in fields:
        create_kwargs["rate_limit"] = 60

    ApiKey.objects.create(**create_kwargs)

    client = APIClient()
    resp = client.post(
        "/v1/public/leads",
        {"name": "Patel", "email": "patel@acme.com"},
        format="json",
        HTTP_X_CHATBOT_KEY=raw_key,
    )

    assert resp.status_code == 200, resp.content
    data = resp.json()
    assert data["lead"]["email"] == "patel@acme.com"

    assert Lead.objects.filter(tenant=tenant, chatbot=bot, primary_email="patel@acme.com").count() == 1
