import pytest
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import RefreshToken

User = get_user_model()

@pytest.mark.django_db
def test_tenant_me_requires_auth(tenant):
    client = APIClient()
    r = client.get("/v1/tenants/me", HTTP_X_TENANT_ID=str(tenant.id))
    assert r.status_code == 401

@pytest.mark.django_db
def test_tenant_me_requires_tenant_header(user):
    client = APIClient()
    refresh = RefreshToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}")
    r = client.get("/v1/tenants/me")
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "TENANT_REQUIRED"
