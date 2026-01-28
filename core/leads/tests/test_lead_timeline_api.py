import uuid
import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from core.chatbots.models import Chatbot
from core.flags.models import FeatureFlag, TenantFeatureFlag
from core.iam.models import TenantMembership
from core.leads.models import Lead
from core.tenants.models import Tenant


@pytest.mark.django_db
def test_lead_timeline_requires_crm_flag(django_user_model):
    api = APIClient()

    user = django_user_model.objects.create_user(username="u1", password="pass123")
    api.force_authenticate(user=user)

    tenant = Tenant.objects.create(id=uuid.uuid4(), name="T1")
    TenantMembership.objects.create(
        tenant_id=tenant.id,
        user_id=user.id,
        role=TenantMembership.ROLE_OWNER,
    )

    # ensure crm flag exists but disabled for this tenant
    FeatureFlag.objects.update_or_create(
        key="crm_enabled",
        defaults={"description": "CRM enabled", "enabled_by_default": False},
    )
    TenantFeatureFlag.objects.filter(tenant_id=tenant.id, key_id="crm_enabled").delete()

    bot = Chatbot.objects.create(
        id=uuid.uuid4(),
        tenant=tenant,
        name="B1",
        status=Chatbot.Status.ACTIVE,
        lead_capture_enabled=True,
    )
    lead = Lead.objects.create(
        id=uuid.uuid4(),
        tenant=tenant,
        chatbot=bot,
        name="Patel",
    )

    r = api.get(
        f"/v1/leads/{lead.id}/timeline",
        HTTP_X_TENANT_ID=str(tenant.id),
    )
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "FEATURE_DISABLED"


@pytest.mark.django_db
def test_lead_timeline_returns_created_and_updated_events(django_user_model):
    api = APIClient()

    user = django_user_model.objects.create_user(username="u2", password="pass123")
    api.force_authenticate(user=user)

    tenant = Tenant.objects.create(id=uuid.uuid4(), name="T1")
    TenantMembership.objects.create(
        tenant_id=tenant.id,
        user_id=user.id,
        role=TenantMembership.ROLE_OWNER,
    )

    # enable CRM for tenant
    FeatureFlag.objects.update_or_create(
        key="crm_enabled",
        defaults={"description": "CRM enabled", "enabled_by_default": False},
    )
    TenantFeatureFlag.objects.update_or_create(
        tenant_id=tenant.id,
        key_id="crm_enabled",
        defaults={"is_enabled": True, "updated_at": timezone.now()},
    )

    bot = Chatbot.objects.create(
        id=uuid.uuid4(),
        tenant=tenant,
        name="B1",
        status=Chatbot.Status.ACTIVE,
        lead_capture_enabled=True,
    )
    lead = Lead.objects.create(
        id=uuid.uuid4(),
        tenant=tenant,
        chatbot=bot,
        name="Patel",
        primary_email="p@a.com",
    )

    # lead.created event should exist (if LeadEvent creation signal is wired)
    r1 = api.get(
        f"/v1/leads/{lead.id}/timeline",
        HTTP_X_TENANT_ID=str(tenant.id),
    )
    assert r1.status_code == 200
    items1 = r1.json()["items"]
    assert any(e["type"] == "lead.created" for e in items1)

    # PATCH -> should create lead.updated event
    r2 = api.patch(
        f"/v1/leads/{lead.id}",
        {"status": "qualified"},
        format="json",
        HTTP_X_TENANT_ID=str(tenant.id),
    )
    assert r2.status_code == 200

    r3 = api.get(
        f"/v1/leads/{lead.id}/timeline",
        HTTP_X_TENANT_ID=str(tenant.id),
    )
    assert r3.status_code == 200
    items3 = r3.json()["items"]
    assert any(e["type"] == "lead.updated" for e in items3)
