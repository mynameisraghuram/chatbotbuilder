import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from core.tenants.models import Tenant
from core.iam.models import TenantMembership
from core.flags.models import FeatureFlag, TenantFeatureFlag
from core.chatbots.models import Chatbot
from core.conversations.models import Conversation, Message


@pytest.mark.django_db
def test_conversations_search_returns_matches():
    User = get_user_model()
    user = User.objects.create_user(username="o1", email="o1@x.com", password="pass12345")
    tenant = Tenant.objects.create(name="T1")
    TenantMembership.objects.create(tenant=tenant, user=user, role=TenantMembership.ROLE_OWNER)

    FeatureFlag.objects.create(key="analytics_enabled", enabled_by_default=False, description="Analytics access")
    TenantFeatureFlag.objects.create(tenant=tenant, key_id="analytics_enabled", is_enabled=True)

    bot = Chatbot.objects.create(
        tenant=tenant,
        name="Bot",
        status=Chatbot.Status.ACTIVE,
        citations_enabled=False,
        lead_capture_enabled=True,
    )

    c1 = Conversation.objects.create(tenant_id=tenant.id, chatbot_id=bot.id)
    m1 = Message.objects.create(tenant_id=tenant.id, conversation=c1, role=Message.Role.USER, content="What is your refund policy?", meta_json={})

    c2 = Conversation.objects.create(tenant_id=tenant.id, chatbot_id=bot.id)
    Message.objects.create(tenant_id=tenant.id, conversation=c2, role=Message.Role.USER, content="Pricing details please", meta_json={})

    refresh = RefreshToken.for_user(user)
    client = APIClient()
    client.credentials(
        HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}",
        HTTP_X_TENANT_ID=str(tenant.id),
    )

    r = client.get(f"/v1/conversations/search?chatbot_id={bot.id}&q=refund&days=30&limit=10&offset=0")
    assert r.status_code == 200, r.content
    j = r.json()

    assert j["page"]["total"] >= 1
    assert any(x["message_id"] == str(m1.id) for x in j["items"])
    assert "refund" in j["items"][0]["snippet"].lower()


@pytest.mark.django_db
def test_conversations_search_requires_q_and_chatbot_id():
    User = get_user_model()
    user = User.objects.create_user(username="o1", email="o1@x.com", password="pass12345")
    tenant = Tenant.objects.create(name="T1")
    TenantMembership.objects.create(tenant=tenant, user=user, role=TenantMembership.ROLE_OWNER)

    FeatureFlag.objects.create(key="analytics_enabled", enabled_by_default=False, description="Analytics access")
    TenantFeatureFlag.objects.create(tenant=tenant, key_id="analytics_enabled", is_enabled=True)

    refresh = RefreshToken.for_user(user)
    client = APIClient()
    client.credentials(
        HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}",
        HTTP_X_TENANT_ID=str(tenant.id),
    )

    r1 = client.get("/v1/conversations/search?q=refund")
    assert r1.status_code == 422

    r2 = client.get("/v1/conversations/search?chatbot_id=00000000-0000-0000-0000-000000000000")
    assert r2.status_code == 422
