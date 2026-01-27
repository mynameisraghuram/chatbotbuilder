import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from core.tenants.models import Tenant
from core.iam.models import TenantMembership
from core.flags.models import FeatureFlag, TenantFeatureFlag
from core.chatbots.models import Chatbot
from core.conversations.models import Conversation, Message
from django.utils import timezone


@pytest.mark.django_db
def test_chatbot_analytics_requires_flag_and_returns_metrics():
    # Setup
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

    conv1 = Conversation.objects.create(tenant_id=tenant.id, chatbot_id=bot.id)
    Message.objects.create(tenant_id=tenant.id, conversation=conv1, role=Message.Role.USER, content="refund policy", meta_json={})
    Message.objects.create(tenant_id=tenant.id, conversation=conv1, role=Message.Role.ASSISTANT, content="ok", meta_json={"kb_used": True, "kb_top_score": 1.2})

    conv2 = Conversation.objects.create(tenant_id=tenant.id, chatbot_id=bot.id)
    Message.objects.create(tenant_id=tenant.id, conversation=conv2, role=Message.Role.USER, content="pricing", meta_json={})
    Message.objects.create(tenant_id=tenant.id, conversation=conv2, role=Message.Role.ASSISTANT, content="no info", meta_json={"kb_used": False, "kb_top_score": 0.0})

    # Auth
    refresh = RefreshToken.for_user(user)
    client = APIClient()
    client.credentials(
        HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}",
        HTTP_X_TENANT_ID=str(tenant.id),
    )

    # Call
    r = client.get(f"/v1/analytics/chatbots/{bot.id}")
    assert r.status_code == 200, r.content
    j = r.json()

    assert j["metrics"]["conversations_total"] == 2
    assert j["metrics"]["assistant_messages_total"] == 2
    assert j["metrics"]["kb_hit_rate"] == 0.5
    assert j["metrics"]["unanswered_rate"] == 0.5

    # Top unanswered queries should include "pricing"
    top = j["top_unanswered_queries"]
    assert any(x["query"] == "pricing" for x in top)
