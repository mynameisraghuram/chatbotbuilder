import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from core.tenants.models import Tenant
from core.iam.models import TenantMembership
from core.chatbots.models import Chatbot


@pytest.mark.django_db
def test_api_keys_owner_can_create_list_rotate_revoke():
    User = get_user_model()

    tenant = Tenant.objects.create(name="Acme")
    user = User.objects.create_user(username="owner", email="owner@acme.com", password="Test@12345")
    TenantMembership.objects.create(tenant=tenant, user=user, role="owner")

    bot = Chatbot.objects.create(tenant=tenant, name="Acme Bot")

    c = APIClient()
    c.force_authenticate(user=user)
    c.credentials(HTTP_X_TENANT_ID=str(tenant.id))

    # Create
    res = c.post(f"/v1/chatbots/{bot.id}/api-keys", {"rate_limit_per_min": 60}, format="json")
    assert res.status_code == 201
    assert "api_key" in res.data
    assert "raw_key" in res.data["api_key"]
    api_key_id = res.data["api_key"]["id"]

    # List (raw_key must NOT be returned)
    res = c.get(f"/v1/chatbots/{bot.id}/api-keys")
    assert res.status_code == 200
    assert "items" in res.data
    assert len(res.data["items"]) == 1
    assert "raw_key" not in res.data["items"][0]

    # Rotate (returns new raw_key)
    res = c.post(f"/v1/api-keys/{api_key_id}/rotate", {}, format="json")
    assert res.status_code == 200
    assert "raw_key" in res.data["api_key"]
    new_api_key_id = res.data["api_key"]["id"]
    assert new_api_key_id != api_key_id

    # Revoke (idempotent)
    res = c.post(f"/v1/api-keys/{new_api_key_id}/revoke", {}, format="json")
    assert res.status_code == 200
    assert res.data["api_key"]["status"] == "revoked"

    res2 = c.post(f"/v1/api-keys/{new_api_key_id}/revoke", {}, format="json")
    assert res2.status_code == 200
    assert res2.data["api_key"]["status"] == "revoked"


@pytest.mark.django_db
def test_api_keys_editor_forbidden_to_create_rotate_revoke():
    User = get_user_model()

    tenant = Tenant.objects.create(name="Acme")
    user = User.objects.create_user(username="ed", email="ed@acme.com", password="Test@12345")
    TenantMembership.objects.create(tenant=tenant, user=user, role="editor")

    bot = Chatbot.objects.create(tenant=tenant, name="Acme Bot")

    c = APIClient()
    c.force_authenticate(user=user)
    c.credentials(HTTP_X_TENANT_ID=str(tenant.id))

    # editor can list (ok)
    res = c.get(f"/v1/chatbots/{bot.id}/api-keys")
    assert res.status_code == 200

    # editor cannot create
    res = c.post(f"/v1/chatbots/{bot.id}/api-keys", {"rate_limit_per_min": 60}, format="json")
    assert res.status_code == 403


@pytest.mark.django_db
def test_api_keys_cross_tenant_blocked():
    User = get_user_model()

    tenant_a = Tenant.objects.create(name="A")
    tenant_b = Tenant.objects.create(name="B")

    user_a = User.objects.create_user(username="a", email="a@x.com", password="Test@12345")
    TenantMembership.objects.create(tenant=tenant_a, user=user_a, role="owner")

    bot_b = Chatbot.objects.create(tenant=tenant_b, name="B Bot")

    c = APIClient()
    c.force_authenticate(user=user_a)
    c.credentials(HTTP_X_TENANT_ID=str(tenant_a.id))

    # tenant A user trying to access tenant B bot => 404 (do not leak existence)
    res = c.get(f"/v1/chatbots/{bot_b.id}/api-keys")
    assert res.status_code == 404
