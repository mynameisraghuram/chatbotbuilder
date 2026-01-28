#backend/core/leads/tests/test_lead_sla_api.py

import uuid
import pytest
from django.utils import timezone
from datetime import timedelta
from rest_framework.test import APIClient

from core.chatbots.models import Chatbot
from core.flags.models import FeatureFlag, TenantFeatureFlag
from core.iam.models import TenantMembership
from core.leads.models import Lead, LeadSlaPolicy, LeadReminder
from core.tenants.models import Tenant
from core.leads.tasks_sla import schedule_lead_reminders


@pytest.mark.django_db
def test_lead_touch_sets_last_contacted_and_next_action(django_user_model):
    api = APIClient()
    user = django_user_model.objects.create_user(username="u_sla", password="pass123")
    api.force_authenticate(user=user)

    tenant = Tenant.objects.create(id=uuid.uuid4(), name="T1")
    TenantMembership.objects.create(tenant_id=tenant.id, user_id=user.id, role=TenantMembership.ROLE_OWNER)

    FeatureFlag.objects.update_or_create(key="crm_enabled", defaults={"description": "CRM", "enabled_by_default": False})
    FeatureFlag.objects.update_or_create(key="lead_sla_enabled", defaults={"description": "SLA", "enabled_by_default": False})

    TenantFeatureFlag.objects.update_or_create(tenant_id=tenant.id, key_id="crm_enabled", defaults={"is_enabled": True, "updated_at": timezone.now()})
    TenantFeatureFlag.objects.update_or_create(tenant_id=tenant.id, key_id="lead_sla_enabled", defaults={"is_enabled": True, "updated_at": timezone.now()})

    LeadSlaPolicy.objects.create(tenant=tenant, is_enabled=True, minutes_by_status={"new": 30})

    bot = Chatbot.objects.create(id=uuid.uuid4(), tenant=tenant, name="B1", status=Chatbot.Status.ACTIVE, lead_capture_enabled=True)
    lead = Lead.objects.create(id=uuid.uuid4(), tenant=tenant, chatbot=bot, name="Patel", status="new")

    r = api.post(f"/v1/leads/{lead.id}/touch", {"note": "called"}, format="json", HTTP_X_TENANT_ID=str(tenant.id))
    assert r.status_code == 200
    lead.refresh_from_db()
    assert lead.last_contacted_at is not None
    assert lead.next_action_at is not None


@pytest.mark.django_db
def test_scheduler_creates_reminder_when_due(django_user_model):
    tenant = Tenant.objects.create(id=uuid.uuid4(), name="T1")

    FeatureFlag.objects.update_or_create(key="crm_enabled", defaults={"description": "CRM", "enabled_by_default": False})
    FeatureFlag.objects.update_or_create(key="lead_sla_enabled", defaults={"description": "SLA", "enabled_by_default": False})

    TenantFeatureFlag.objects.update_or_create(tenant_id=tenant.id, key_id="crm_enabled", defaults={"is_enabled": True, "updated_at": timezone.now()})
    TenantFeatureFlag.objects.update_or_create(tenant_id=tenant.id, key_id="lead_sla_enabled", defaults={"is_enabled": True, "updated_at": timezone.now()})

    bot = Chatbot.objects.create(id=uuid.uuid4(), tenant=tenant, name="B1", status=Chatbot.Status.ACTIVE, lead_capture_enabled=True)
    lead = Lead.objects.create(
        id=uuid.uuid4(),
        tenant=tenant,
        chatbot=bot,
        name="Patel",
        status="new",
        next_action_at=timezone.now() - timedelta(minutes=1),
    )

    schedule_lead_reminders()

    assert LeadReminder.objects.filter(tenant=tenant, lead=lead).exists()
