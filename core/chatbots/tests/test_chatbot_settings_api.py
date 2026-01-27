import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from core.tenants.models import Tenant
from core.iam.models import TenantMembership
from core.chatbots.models import Chatbot


@pytest.mark.django_db
def test_chatbot_toggle_lead_capture_owner_ok():
    User = get_user_model()
    user = User.objects.create_user(username="o1", email="o1@x.com", password="pass12345")
    tenant = Tenant.objects.create(name="T1")
    TenantMembership.objects.create(tenant=tenant, user=user, role=TenantMembership.ROLE_OWNER)

    bot = Chatbot.objects.create(
        tenant=tenant,
        name="B1",
        status=Chatbot.Status.ACTIVE,
        citations_enabled=False,
        lead_capture_enabled=False,
    )

    refresh = RefreshToken.for_user(user)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}", HTTP_X_TENANT_ID=str(tenant.id))

    resp = client.patch(f"/v1/chatbots/{bot.id}", {"lead_capture_enabled": True}, format="json")
    assert resp.status_code == 200, resp.content
    assert resp.json()["chatbot"]["lead_capture_enabled"] is True


@pytest.mark.django_db
def test_chatbot_toggle_lead_capture_viewer_forbidden():
    User = get_user_model()
    user = User.objects.create_user(username="v1", email="v1@x.com", password="pass12345")
    tenant = Tenant.objects.create(name="T2")
    TenantMembership.objects.create(tenant=tenant, user=user, role=TenantMembership.ROLE_VIEWER)

    bot = Chatbot.objects.create(
        tenant=tenant,
        name="B2",
        status=Chatbot.Status.ACTIVE,
        citations_enabled=False,
        lead_capture_enabled=False,
    )

    refresh = RefreshToken.for_user(user)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}", HTTP_X_TENANT_ID=str(tenant.id))

    resp = client.patch(f"/v1/chatbots/{bot.id}", {"lead_capture_enabled": True}, format="json")
    assert resp.status_code == 403
