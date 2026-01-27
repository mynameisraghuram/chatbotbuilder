import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from core.tenants.models import Tenant
from core.iam.models import TenantMembership


@pytest.mark.django_db
def test_chatbot_create_requires_tenant_header():
    c = APIClient()
    res = c.post("/v1/chatbots/", {"name": "Bot"}, format="json")
    assert res.status_code in (400, 401, 403)


@pytest.mark.django_db
def test_chatbot_create_owner_ok():
    User = get_user_model()

    tenant = Tenant.objects.create(name="Acme")

    # Your user model requires 'username'
    user = User.objects.create_user(
        username="owner",
        email="owner@acme.com",
        password="Test@12345",
    )

    TenantMembership.objects.create(tenant=tenant, user=user, role="owner")

    c = APIClient()
    c.force_authenticate(user=user)
    c.credentials(HTTP_X_TENANT_ID=str(tenant.id))

    res = c.post("/v1/chatbots/", {"name": "Bot"}, format="json")
    assert res.status_code == 201
    assert res.data["name"] == "Bot"
