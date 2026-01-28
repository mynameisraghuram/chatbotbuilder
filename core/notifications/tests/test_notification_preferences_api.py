import uuid
import pytest
from rest_framework.test import APIClient

from core.iam.models import TenantMembership
from core.tenants.models import Tenant


@pytest.mark.django_db
def test_my_notification_preferences_get_and_patch(django_user_model):
    api = APIClient()
    user = django_user_model.objects.create_user(username="u1", password="pass123")
    api.force_authenticate(user=user)

    tenant = Tenant.objects.create(id=uuid.uuid4(), name="T1")
    TenantMembership.objects.create(tenant_id=tenant.id, user_id=user.id, role=TenantMembership.ROLE_OWNER)

    r1 = api.get("/v1/notifications/preferences/me", HTTP_X_TENANT_ID=str(tenant.id))
    assert r1.status_code == 200
    prefs = r1.json()["preferences"]
    assert prefs["email_enabled"] is True
    assert prefs["digest_mode"] == "off"

    r2 = api.patch(
        "/v1/notifications/preferences/me",
        {"email_enabled": False, "digest_mode": "daily", "digest_hour": 10},
        format="json",
        HTTP_X_TENANT_ID=str(tenant.id),
    )
    assert r2.status_code == 200
    prefs2 = r2.json()["preferences"]
    assert prefs2["email_enabled"] is False
    assert prefs2["digest_mode"] == "daily"
    assert prefs2["digest_hour"] == 10
