import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from core.tenants.models import Tenant
from core.iam.models import TenantMembership
from core.flags.models import FeatureFlag, TenantFeatureFlag
from core.chatbots.models import Chatbot
from core.conversations.models import Conversation
from core.leads.models import Lead


@pytest.mark.django_db
def test_conversation_lead_link_requires_crm_flag():
    User = get_user_model()
    user = User.objects.create_user(username="o1", email="o1@x.com", password="pass12345")
    tenant = Tenant.objects.create(name="T1")
    TenantMembership.objects.create(tenant=tenant, user=user, role=TenantMembership.ROLE_OWNER)

    # crm disabled by default unless enabled for tenant
    FeatureFlag.objects.create(key="crm_enabled", enabled_by_default=False, description="CRM access")

    bot = Chatbot.objects.create(tenant=tenant, name="Bot", status=Chatbot.Status.ACTIVE)
    conv = Conversation.objects.create(tenant_id=tenant.id, chatbot_id=bot.id)
    lead = Lead.objects.create(tenant_id=tenant.id)

    refresh = RefreshToken.for_user(user)
    client = APIClient()
    client.credentials(
        HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}",
        HTTP_X_TENANT_ID=str(tenant.id),
    )

    r = client.post(f"/v1/conversations/{conv.id}/lead/link", {"lead_id": str(lead.id)}, format="json")
    assert r.status_code == 403


@pytest.mark.django_db
def test_conversation_lead_link_owner_ok_and_get_ok():
    User = get_user_model()
    user = User.objects.create_user(username="o2", email="o2@x.com", password="pass12345")
    tenant = Tenant.objects.create(name="T2")
    TenantMembership.objects.create(tenant=tenant, user=user, role=TenantMembership.ROLE_OWNER)

    FeatureFlag.objects.create(key="crm_enabled", enabled_by_default=False, description="CRM access")
    TenantFeatureFlag.objects.create(tenant=tenant, key_id="crm_enabled", is_enabled=True)

    bot = Chatbot.objects.create(tenant=tenant, name="Bot", status=Chatbot.Status.ACTIVE)
    conv = Conversation.objects.create(tenant_id=tenant.id, chatbot_id=bot.id)
    lead = Lead.objects.create(tenant_id=tenant.id)

    refresh = RefreshToken.for_user(user)
    client = APIClient()
    client.credentials(
        HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}",
        HTTP_X_TENANT_ID=str(tenant.id),
    )

    r1 = client.post(f"/v1/conversations/{conv.id}/lead/link", {"lead_id": str(lead.id)}, format="json")
    assert r1.status_code == 200, r1.content
    assert r1.json()["lead"]["id"] == str(lead.id)

    r2 = client.get(f"/v1/conversations/{conv.id}/lead")
    assert r2.status_code == 200, r2.content
    assert r2.json()["lead"]["id"] == str(lead.id)

    # unlink
    r3 = client.post(f"/v1/conversations/{conv.id}/lead/link", {"lead_id": None}, format="json")
    assert r3.status_code == 200
    assert r3.json()["lead"] is None


@pytest.mark.django_db
def test_conversation_lead_link_forbidden_for_viewer():
    User = get_user_model()
    user = User.objects.create_user(username="v1", email="v1@x.com", password="pass12345")
    tenant = Tenant.objects.create(name="T3")
    TenantMembership.objects.create(tenant=tenant, user=user, role=TenantMembership.ROLE_VIEWER)

    FeatureFlag.objects.create(key="crm_enabled", enabled_by_default=False, description="CRM access")
    TenantFeatureFlag.objects.create(tenant=tenant, key_id="crm_enabled", is_enabled=True)

    bot = Chatbot.objects.create(tenant=tenant, name="Bot", status=Chatbot.Status.ACTIVE)
    conv = Conversation.objects.create(tenant_id=tenant.id, chatbot_id=bot.id)
    lead = Lead.objects.create(tenant_id=tenant.id)

    refresh = RefreshToken.for_user(user)
    client = APIClient()
    client.credentials(
        HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}",
        HTTP_X_TENANT_ID=str(tenant.id),
    )

    r = client.post(f"/v1/conversations/{conv.id}/lead/link", {"lead_id": str(lead.id)}, format="json")
    assert r.status_code == 403
