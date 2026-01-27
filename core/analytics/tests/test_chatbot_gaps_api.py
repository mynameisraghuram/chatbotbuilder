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
def test_chatbot_gaps_returns_unanswered_with_examples():
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

    # Unanswered conversation (kb_used false)
    c1 = Conversation.objects.create(tenant_id=tenant.id, chatbot_id=bot.id)
    Message.objects.create(tenant_id=tenant.id, conversation=c1, role=Message.Role.USER, content="pricing", meta_json={})
    Message.objects.create(tenant_id=tenant.id, conversation=c1, role=Message.Role.ASSISTANT, content="no", meta_json={"kb_used": False})

    # Another unanswered conversation (kb_used missing => counts as unanswered)
    c2 = Conversation.objects.create(tenant_id=tenant.id, chatbot_id=bot.id)
    Message.objects.create(tenant_id=tenant.id, conversation=c2, role=Message.Role.USER, content="pricing", meta_json={})
    Message.objects.create(tenant_id=tenant.id, conversation=c2, role=Message.Role.ASSISTANT, content="no", meta_json={})

    # Answered conversation shouldn't affect gaps
    c3 = Conversation.objects.create(tenant_id=tenant.id, chatbot_id=bot.id)
    Message.objects.create(tenant_id=tenant.id, conversation=c3, role=Message.Role.USER, content="refund policy", meta_json={})
    Message.objects.create(tenant_id=tenant.id, conversation=c3, role=Message.Role.ASSISTANT, content="ok", meta_json={"kb_used": True})

    refresh = RefreshToken.for_user(user)
    client = APIClient()
    client.credentials(
        HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}",
        HTTP_X_TENANT_ID=str(tenant.id),
    )

    r = client.get(f"/v1/analytics/chatbots/{bot.id}/gaps?days=30&limit=10")
    assert r.status_code == 200, r.content
    j = r.json()

    gaps = j["unanswered_queries"]
    assert any(x["query"] == "pricing" and x["count"] == 2 for x in gaps)

    pricing = [x for x in gaps if x["query"] == "pricing"][0]
    assert len(pricing["examples"]) >= 1
