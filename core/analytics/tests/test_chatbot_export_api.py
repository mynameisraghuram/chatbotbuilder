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
def test_chatbot_export_contains_all_sections():
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

    # answered
    c1 = Conversation.objects.create(tenant_id=tenant.id, chatbot_id=bot.id)
    Message.objects.create(tenant_id=tenant.id, conversation=c1, role=Message.Role.USER, content="refund policy", meta_json={})
    Message.objects.create(tenant_id=tenant.id, conversation=c1, role=Message.Role.ASSISTANT, content="ok", meta_json={"kb_used": True})

    # unanswered
    c2 = Conversation.objects.create(tenant_id=tenant.id, chatbot_id=bot.id)
    Message.objects.create(tenant_id=tenant.id, conversation=c2, role=Message.Role.USER, content="pricing", meta_json={})
    Message.objects.create(tenant_id=tenant.id, conversation=c2, role=Message.Role.ASSISTANT, content="no", meta_json={"kb_used": False})

    refresh = RefreshToken.for_user(user)
    client = APIClient()
    client.credentials(
        HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}",
        HTTP_X_TENANT_ID=str(tenant.id),
    )

    r = client.get(f"/v1/analytics/chatbots/{bot.id}/export?days=30&limit=10")
    assert r.status_code == 200, r.content
    j = r.json()

    assert "summary" in j
    assert "trends" in j and "series" in j["trends"]
    assert "top_queries" in j and "top_queries" in j["top_queries"]
    assert "gaps" in j and "unanswered_queries" in j["gaps"]

    # should include pricing gap
    assert any(x["query"] == "pricing" for x in j["gaps"]["unanswered_queries"])
