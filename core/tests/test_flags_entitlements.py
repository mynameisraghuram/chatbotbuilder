import pytest

@pytest.mark.django_db
def test_entitlements_requires_membership(auth_client, tenant):
    r = auth_client.get("/v1/entitlements", HTTP_X_TENANT_ID=str(tenant.id))
    assert r.status_code == 403

@pytest.mark.django_db
def test_entitlements_returns_flags(auth_client, tenant, membership, flags_catalog, tenant_flag_override):
    r = auth_client.get("/v1/entitlements", HTTP_X_TENANT_ID=str(tenant.id))
    assert r.status_code == 200
    body = r.json()
    assert body["flags"]["crm_enabled"] is True
