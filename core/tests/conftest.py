import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from core.tenants.models import Tenant
from core.iam.models import TenantMembership
from core.flags.models import FeatureFlag, TenantFeatureFlag

User = get_user_model()

@pytest.fixture
def tenant(db):
    return Tenant.objects.create(name="Acme", status="active")

@pytest.fixture
def user(db):
    return User.objects.create_user(username="owner", email="owner@acme.com", password="pass12345")

@pytest.fixture
def membership(db, tenant, user):
    return TenantMembership.objects.create(tenant=tenant, user=user, role=TenantMembership.ROLE_OWNER)

@pytest.fixture
def auth_client(user):
    client = APIClient()
    refresh = RefreshToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}")
    return client

@pytest.fixture
def flags_catalog(db):
    FeatureFlag.objects.create(key="crm_enabled", enabled_by_default=False, description="CRM module access")
    FeatureFlag.objects.create(key="analytics_enabled", enabled_by_default=False, description="Analytics access")
    return True

@pytest.fixture
def tenant_flag_override(db, tenant, flags_catalog):
    # Enable CRM for this tenant
    tf = TenantFeatureFlag.objects.create(tenant=tenant, key_id="crm_enabled", is_enabled=True)
    return tf
