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
def test_conversations_list_and_detail_requires_analytics_flag():
    User = get_user_model()
    user = User.objects.create_user(username="u1", email="u1@x.com", password="pass12345")
    tenant = Tenant.objects.create(name="T1")
    TenantMembership.objects.create(tenant=tenant, user=user, role=TenantMembership.ROLE_VIEWER)

    FeatureFlag.objects.create(key="analytics_enabled", enabled_by_default=False, description="Analytics access")
    TenantFeatureFlag.objects.create(tenant=tenant, key_id="analytics_enabled", is_enabled=True)

    bot = Chatbot.objects.create(
        tenant=tenant,
        name="Bot",
        status=Chatbot.Status.ACTIVE,
        citations_enabled=False,
        lead_capture_enabled=True,
    )

    conv = Conversation.objects.create(tenant_id=tenant.id, chatbot_id=bot.id, user_email="x@y.com")
    Message.objects.create(tenant_id=tenant.id, conversation=conv, role=Message.Role.USER, content="pricing", meta_json={})
    Message.objects.create(tenant_id=tenant.id, conversation=conv, role=Message.Role.ASSISTANT, content="no", meta_json={"kb_used": False})

    refresh = RefreshToken.for_user(user)
    client = APIClient()
    client.credentials(
        HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}",
        HTTP_X_TENANT_ID=str(tenant.id),
    )

    # list
    r1 = client.get(f"/v1/conversations?chatbot_id={bot.id}&days=30&limit=10&offset=0")
    assert r1.status_code == 200, r1.content
    j1 = r1.json()
    assert j1["page"]["total"] == 1
    assert j1["items"][0]["id"] == str(conv.id)

    # detail
    r2 = client.get(f"/v1/conversations/{conv.id}")
    assert r2.status_code == 200, r2.content
    j2 = r2.json()
    assert j2["conversation"]["id"] == str(conv.id)
    assert len(j2["conversation"]["messages"]) == 2
