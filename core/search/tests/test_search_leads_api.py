import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from core.tenants.models import Tenant
from core.iam.models import TenantMembership
from core.flags.models import FeatureFlag, TenantFeatureFlag
from core.leads.models import Lead
from core.chatbots.models import Chatbot


@pytest.mark.django_db
def test_search_leads_requires_q():
    User = get_user_model()
    user = User.objects.create_user(username="u1", email="u1@x.com", password="pass12345")
    tenant = Tenant.objects.create(name="T")
    TenantMembership.objects.create(tenant=tenant, user=user, role=TenantMembership.ROLE_OWNER)

    FeatureFlag.objects.create(key="crm_enabled", enabled_by_default=False, description="CRM")
    TenantFeatureFlag.objects.create(tenant=tenant, key_id="crm_enabled", is_enabled=True)

    refresh = RefreshToken.for_user(user)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}", HTTP_X_TENANT_ID=str(tenant.id))

    r = client.get("/v1/search/leads")
    assert r.status_code == 422


@pytest.mark.django_db
def test_search_leads_fallback_to_postgres(monkeypatch):
    # Force OpenSearch path to fail => postgres fallback
    monkeypatch.setattr("core.search.leads_api.search_leads_os", lambda **kwargs: (_ for _ in ()).throw(Exception("OS down")))

    User = get_user_model()
    user = User.objects.create_user(username="u2", email="u2@x.com", password="pass12345")
    tenant = Tenant.objects.create(name="T2")
    TenantMembership.objects.create(tenant=tenant, user=user, role=TenantMembership.ROLE_OWNER)

    FeatureFlag.objects.create(key="crm_enabled", enabled_by_default=False, description="CRM")
    TenantFeatureFlag.objects.create(tenant=tenant, key_id="crm_enabled", is_enabled=True)

    bot = Chatbot.objects.create(tenant=tenant, name="B", status=Chatbot.Status.ACTIVE, citations_enabled=False, lead_capture_enabled=True)
    Lead.objects.create(tenant=tenant, chatbot=bot, name="Patel", primary_email="patel@acme.com")

    refresh = RefreshToken.for_user(user)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}", HTTP_X_TENANT_ID=str(tenant.id))

    r = client.get("/v1/search/leads?q=patel")
    assert r.status_code == 200
    j = r.json()
    assert j["source"] == "postgres"
    assert j["page"]["total"] == 1
