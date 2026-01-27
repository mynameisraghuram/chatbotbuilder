import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken
from django.utils import timezone
from datetime import timedelta

from core.tenants.models import Tenant
from core.iam.models import TenantMembership
from core.flags.models import FeatureFlag, TenantFeatureFlag
from core.chatbots.models import Chatbot
from core.conversations.models import Conversation, Message


@pytest.mark.django_db
def test_chatbot_trends_returns_dense_series():
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

    # Create activity "today"
    conv = Conversation.objects.create(tenant_id=tenant.id, chatbot_id=bot.id)
    Message.objects.create(tenant_id=tenant.id, conversation=conv, role=Message.Role.USER, content="hi", meta_json={})
    Message.objects.create(tenant_id=tenant.id, conversation=conv, role=Message.Role.ASSISTANT, content="ok", meta_json={"kb_used": True})

    refresh = RefreshToken.for_user(user)
    client = APIClient()
    client.credentials(
        HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}",
        HTTP_X_TENANT_ID=str(tenant.id),
    )

    r = client.get(f"/v1/analytics/chatbots/{bot.id}/trends?days=7")
    assert r.status_code == 200, r.content
    j = r.json()

    assert j["days"] == 7
    assert len(j["series"]) == 7

    # Today should have at least 1 user/assistant message
    today = timezone.now().date().isoformat()
    row = [x for x in j["series"] if x["day"] == today][0]
    assert row["user_messages_count"] >= 1
    assert row["assistant_messages_count"] >= 1
    assert row["kb_hit_rate"] in (0.0, 1.0)  # here should be 1.0
