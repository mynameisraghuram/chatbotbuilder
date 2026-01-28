import uuid
import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from core.chatbots.models import Chatbot
from core.flags.models import FeatureFlag, TenantFeatureFlag
from core.iam.models import TenantMembership
from core.leads.models import Lead
from core.tenants.models import Tenant


@pytest.mark.django_db
def test_lead_notes_crud_and_timeline_events(django_user_model):
    api = APIClient()
    user = django_user_model.objects.create_user(username="u_notes", password="pass123")
    api.force_authenticate(user=user)

    tenant = Tenant.objects.create(id=uuid.uuid4(), name="T1")
    TenantMembership.objects.create(
        tenant_id=tenant.id,
        user_id=user.id,
        role=TenantMembership.ROLE_OWNER,
    )

    # enable CRM
    FeatureFlag.objects.update_or_create(
        key="crm_enabled",
        defaults={"description": "CRM enabled", "enabled_by_default": False},
    )
    TenantFeatureFlag.objects.update_or_create(
        tenant_id=tenant.id,
        key_id="crm_enabled",
        defaults={"is_enabled": True, "updated_at": timezone.now()},
    )

    bot = Chatbot.objects.create(
        id=uuid.uuid4(),
        tenant=tenant,
        name="B1",
        status=Chatbot.Status.ACTIVE,
        lead_capture_enabled=True,
    )
    lead = Lead.objects.create(
        id=uuid.uuid4(),
        tenant=tenant,
        chatbot=bot,
        name="Patel",
    )

    # create note
    r1 = api.post(
        f"/v1/leads/{lead.id}/notes",
        {"body": "Customer asked about pricing and demo."},
        format="json",
        HTTP_X_TENANT_ID=str(tenant.id),
    )
    assert r1.status_code == 201
    note_id = r1.json()["note"]["id"]

    # list notes
    r2 = api.get(
        f"/v1/leads/{lead.id}/notes",
        HTTP_X_TENANT_ID=str(tenant.id),
    )
    assert r2.status_code == 200
    assert len(r2.json()["items"]) == 1

    # update note
    r3 = api.patch(
        f"/v1/leads/{lead.id}/notes/{note_id}",
        {"body": "Customer asked about pricing + wants a demo next week."},
        format="json",
        HTTP_X_TENANT_ID=str(tenant.id),
    )
    assert r3.status_code == 200

    # delete note
    r4 = api.delete(
        f"/v1/leads/{lead.id}/notes/{note_id}",
        HTTP_X_TENANT_ID=str(tenant.id),
    )
    assert r4.status_code == 204

    # ensure timeline has note events
    r5 = api.get(
        f"/v1/leads/{lead.id}/timeline",
        HTTP_X_TENANT_ID=str(tenant.id),
    )
    assert r5.status_code == 200
    items = r5.json()["items"]
    assert any(e["type"] == "lead.note.created" for e in items)
    assert any(e["type"] == "lead.note.updated" for e in items)
    assert any(e["type"] == "lead.note.deleted" for e in items)
