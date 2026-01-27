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
def test_conversations_list_masks_pii_for_viewer_even_if_requested():
    User = get_user_model()
    user = User.objects.create_user(username="v1", email="v1@x.com", password="pass12345")
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

    conv = Conversation.objects.create(
        tenant_id=tenant.id,
        chatbot_id=bot.id,
        user_email="secret@example.com",
        external_user_id="ext-123",
        session_id="sess-123",
    )
    Message.objects.create(tenant_id=tenant.id, conversation=conv, role=Message.Role.USER, content="hi", meta_json={})
    Message.objects.create(tenant_id=tenant.id, conversation=conv, role=Message.Role.ASSISTANT, content="ok", meta_json={"kb_used": True})

    refresh = RefreshToken.for_user(user)
    client = APIClient()
    client.credentials(
        HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}",
        HTTP_X_TENANT_ID=str(tenant.id),
    )

    r = client.get(f"/v1/conversations?chatbot_id={bot.id}&days=30&include_pii=true")
    assert r.status_code == 200, r.content
    item = r.json()["items"][0]
    assert item["user_email"] == ""
    assert item["external_user_id"] == ""
    assert item["session_id"] == ""


@pytest.mark.django_db
def test_conversations_list_allows_pii_for_owner_with_include_pii():
    User = get_user_model()
    user = User.objects.create_user(username="o1", email="o1@x.com", password="pass12345")
    tenant = Tenant.objects.create(name="T2")
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

    conv = Conversation.objects.create(
        tenant_id=tenant.id,
        chatbot_id=bot.id,
        user_email="ownercansee@example.com",
        external_user_id="ext-999",
        session_id="sess-999",
    )
    Message.objects.create(tenant_id=tenant.id, conversation=conv, role=Message.Role.USER, content="hi", meta_json={})
    Message.objects.create(tenant_id=tenant.id, conversation=conv, role=Message.Role.ASSISTANT, content="ok", meta_json={"kb_used": True})

    refresh = RefreshToken.for_user(user)
    client = APIClient()
    client.credentials(
        HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}",
        HTTP_X_TENANT_ID=str(tenant.id),
    )

    r = client.get(f"/v1/conversations?chatbot_id={bot.id}&days=30&include_pii=true")
    assert r.status_code == 200, r.content
    item = r.json()["items"][0]
    assert item["user_email"] == "ownercansee@example.com"
    assert item["external_user_id"] == "ext-999"
    assert item["session_id"] == "sess-999"


@pytest.mark.django_db
def test_conversations_list_kb_used_filter_true_false():
    User = get_user_model()
    user = User.objects.create_user(username="o2", email="o2@x.com", password="pass12345")
    tenant = Tenant.objects.create(name="T3")
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

    c_true = Conversation.objects.create(tenant_id=tenant.id, chatbot_id=bot.id)
    Message.objects.create(tenant_id=tenant.id, conversation=c_true, role=Message.Role.ASSISTANT, content="ok", meta_json={"kb_used": True})

    c_false = Conversation.objects.create(tenant_id=tenant.id, chatbot_id=bot.id)
    Message.objects.create(tenant_id=tenant.id, conversation=c_false, role=Message.Role.ASSISTANT, content="no", meta_json={"kb_used": False})

    refresh = RefreshToken.for_user(user)
    client = APIClient()
    client.credentials(
        HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}",
        HTTP_X_TENANT_ID=str(tenant.id),
    )

    r1 = client.get(f"/v1/conversations?chatbot_id={bot.id}&days=30&kb_used=true")
    assert r1.status_code == 200, r1.content
    ids_true = {x["id"] for x in r1.json()["items"]}
    assert str(c_true.id) in ids_true
    assert str(c_false.id) not in ids_true

    r2 = client.get(f"/v1/conversations?chatbot_id={bot.id}&days=30&kb_used=false")
    assert r2.status_code == 200, r2.content
    ids_false = {x["id"] for x in r2.json()["items"]}
    assert str(c_false.id) in ids_false
