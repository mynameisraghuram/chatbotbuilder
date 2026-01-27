import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from core.tenants.models import Tenant
from core.iam.models import TenantMembership
from core.chatbots.models import Chatbot


@pytest.mark.django_db
def test_public_chat_requires_key():
    c = APIClient()
    res = c.post("/v1/public/chat", {"message": "hi"}, format="json")
    assert res.status_code == 401


@pytest.mark.django_db
def test_public_chat_works_with_key():
    User = get_user_model()

    tenant = Tenant.objects.create(name="Acme")
    user = User.objects.create_user(username="owner", email="owner@acme.com", password="Test@12345")
    TenantMembership.objects.create(tenant=tenant, user=user, role="owner")

    bot = Chatbot.objects.create(tenant=tenant, name="Acme Bot")

    # create api key via dashboard endpoint
    dash = APIClient()
    dash.force_authenticate(user=user)
    dash.credentials(HTTP_X_TENANT_ID=str(tenant.id))
    res = dash.post(f"/v1/chatbots/{bot.id}/api-keys", {"rate_limit_per_min": 60}, format="json")
    assert res.status_code == 201
    raw_key = res.data["api_key"]["raw_key"]

    pub = APIClient()
    pub.credentials(HTTP_X_CHATBOT_KEY=raw_key)

    res2 = pub.post("/v1/public/chat", {"message": "hello"}, format="json")
    assert res2.status_code == 200
    assert "conversation_id" in res2.data
    assert "reply" in res2.data
