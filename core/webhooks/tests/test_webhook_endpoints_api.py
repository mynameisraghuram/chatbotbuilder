import uuid
import pytest
from rest_framework.test import APIClient
from django.utils import timezone

from core.flags.models import FeatureFlag, TenantFeatureFlag
from core.iam.models import TenantMembership
from core.tenants.models import Tenant


@pytest.mark.django_db
def test_webhooks_requires_flag(django_user_model):
    api = APIClient()
    user = django_user_model.objects.create_user(username="u1", password="pass123")
    api.force_authenticate(user=user)

    tenant = Tenant.objects.create(id=uuid.uuid4(), name="T1")
    TenantMembership.objects.create(tenant_id=tenant.id, user_id=user.id, role=TenantMembership.ROLE_OWNER)

    FeatureFlag.objects.update_or_create(
        key="webhooks_enabled",
        defaults={"description": "Webhooks enabled", "enabled_by_default": False},
    )
    TenantFeatureFlag.objects.filter(tenant_id=tenant.id, key_id="webhooks_enabled").delete()

    r = api.get("/v1/webhooks/endpoints", HTTP_X_TENANT_ID=str(tenant.id))
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "FEATURE_DISABLED"


@pytest.mark.django_db
def test_webhooks_crud_and_rotate_secret_owner_only(django_user_model):
    api = APIClient()

    owner = django_user_model.objects.create_user(username="owner", password="pass123")
    viewer = django_user_model.objects.create_user(username="viewer", password="pass123")

    tenant = Tenant.objects.create(id=uuid.uuid4(), name="T1")
    TenantMembership.objects.create(tenant_id=tenant.id, user_id=owner.id, role=TenantMembership.ROLE_OWNER)
    TenantMembership.objects.create(tenant_id=tenant.id, user_id=viewer.id, role=TenantMembership.ROLE_VIEWER)

    FeatureFlag.objects.update_or_create(
        key="webhooks_enabled",
        defaults={"description": "Webhooks enabled", "enabled_by_default": False},
    )
    TenantFeatureFlag.objects.update_or_create(
        tenant_id=tenant.id,
        key_id="webhooks_enabled",
        defaults={"is_enabled": True, "updated_at": timezone.now()},
    )

    # viewer cannot create
    api.force_authenticate(user=viewer)
    r_forbidden = api.post(
        "/v1/webhooks/endpoints",
        {"url": "https://example.com/hook", "events": ["lead.reminder.due"]},
        format="json",
        HTTP_X_TENANT_ID=str(tenant.id),
    )
    assert r_forbidden.status_code == 403

    # owner can create and gets secret
    api.force_authenticate(user=owner)
    r1 = api.post(
        "/v1/webhooks/endpoints",
        {"url": "https://example.com/hook", "events": ["lead.reminder.due"]},
        format="json",
        HTTP_X_TENANT_ID=str(tenant.id),
    )
    assert r1.status_code == 201
    ep = r1.json()["endpoint"]
    assert ep["url"] == "https://example.com/hook"
    assert "secret" in ep and ep["secret"]

    endpoint_id = ep["id"]

    # list
    r2 = api.get("/v1/webhooks/endpoints", HTTP_X_TENANT_ID=str(tenant.id))
    assert r2.status_code == 200
    assert len(r2.json()["items"]) == 1

    # patch
    r3 = api.patch(
        f"/v1/webhooks/endpoints/{endpoint_id}",
        {"is_active": False},
        format="json",
        HTTP_X_TENANT_ID=str(tenant.id),
    )
    assert r3.status_code == 200
    assert r3.json()["endpoint"]["is_active"] is False

    # rotate secret
    r4 = api.post(
        f"/v1/webhooks/endpoints/{endpoint_id}/rotate-secret",
        {},
        format="json",
        HTTP_X_TENANT_ID=str(tenant.id),
    )
    assert r4.status_code == 200
    assert r4.json()["secret"]
