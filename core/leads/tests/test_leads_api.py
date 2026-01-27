# repo-root/backend/core/leads/tests/test_leads_api.py

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from core.tenants.models import Tenant
from core.iam.models import TenantMembership
from core.leads.models import Lead
from core.flags.models import FeatureFlag, TenantFeatureFlag
from core.chatbots.models import Chatbot


@pytest.mark.django_db
def test_leads_list_requires_crm_flag():
    User = get_user_model()
    user = User.objects.create_user(username="u1", email="u1@x.com", password="pass12345")
    tenant = Tenant.objects.create(name="Acme")
    TenantMembership.objects.create(tenant=tenant, user=user, role=TenantMembership.ROLE_OWNER)

    refresh = RefreshToken.for_user(user)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}", HTTP_X_TENANT_ID=str(tenant.id))

    # Ensure catalog exists but crm disabled by default
    FeatureFlag.objects.create(key="crm_enabled", enabled_by_default=False, description="CRM module access")

    resp = client.get("/v1/leads")
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FEATURE_DISABLED"


@pytest.mark.django_db
def test_leads_list_and_patch_owner_ok():
    User = get_user_model()
    user = User.objects.create_user(username="u2", email="u2@x.com", password="pass12345")
    tenant = Tenant.objects.create(name="Acme2")
    TenantMembership.objects.create(tenant=tenant, user=user, role=TenantMembership.ROLE_OWNER)

    FeatureFlag.objects.create(key="crm_enabled", enabled_by_default=False, description="CRM module access")
    TenantFeatureFlag.objects.create(tenant=tenant, key_id="crm_enabled", is_enabled=True)

    bot = Chatbot.objects.create(tenant=tenant, name="Bot", status=Chatbot.Status.ACTIVE, citations_enabled=False)
    lead = Lead.objects.create(tenant=tenant, chatbot=bot, name="Patel", primary_email="patel@acme.com", phone="999")

    refresh = RefreshToken.for_user(user)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}", HTTP_X_TENANT_ID=str(tenant.id))

    r1 = client.get("/v1/leads")
    assert r1.status_code == 200
    assert r1.json()["page"]["total"] == 1

    r2 = client.patch(f"/v1/leads/{lead.id}", {"status": "qualified", "meta": {"source": "chat"}}, format="json")
    assert r2.status_code == 200
    assert r2.json()["lead"]["status"] == "qualified"


@pytest.mark.django_db
def test_leads_patch_viewer_forbidden():
    User = get_user_model()
    user = User.objects.create_user(username="u3", email="u3@x.com", password="pass12345")
    tenant = Tenant.objects.create(name="Acme3")
    TenantMembership.objects.create(tenant=tenant, user=user, role=TenantMembership.ROLE_VIEWER)

    FeatureFlag.objects.create(key="crm_enabled", enabled_by_default=False, description="CRM module access")
    TenantFeatureFlag.objects.create(tenant=tenant, key_id="crm_enabled", is_enabled=True)

    bot = Chatbot.objects.create(tenant=tenant, name="Bot3", status=Chatbot.Status.ACTIVE, citations_enabled=False)
    lead = Lead.objects.create(tenant=tenant, chatbot=bot, name="A", primary_email="a@a.com")

    refresh = RefreshToken.for_user(user)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}", HTTP_X_TENANT_ID=str(tenant.id))

    resp = client.patch(f"/v1/leads/{lead.id}", {"status": "open"}, format="json")
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN"
