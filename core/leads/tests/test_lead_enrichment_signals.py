import uuid
from django.test import TestCase
from django.utils import timezone

from core.tenants.models import Tenant
from core.chatbots.models import Chatbot
from core.conversations.models import Conversation, Message
from core.flags.models import FeatureFlag, TenantFeatureFlag
from core.leads.models import Lead
from core.leads.tasks import enrich_conversation_signals


class LeadEnrichmentSignalsTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(id=uuid.uuid4(), name="T1")
        self.bot = Chatbot.objects.create(
            id=uuid.uuid4(),
            tenant=self.tenant,
            name="Bot",
            status=Chatbot.Status.ACTIVE,
            lead_capture_enabled=True,
        )
        self.convo = Conversation.objects.create(
            id=uuid.uuid4(),
            tenant=self.tenant,
            chatbot=self.bot,
        )

        # Enable flag for this tenant
        FeatureFlag.objects.update_or_create(
            key="lead_enrichment_enabled",
            defaults={"description": "Enable lead enrichment signals", "enabled_by_default": False},
        )
        TenantFeatureFlag.objects.update_or_create(
            tenant=self.tenant,
            key_id="lead_enrichment_enabled",
            defaults={"is_enabled": True},
        )

    def test_enrichment_writes_conversation_and_lead_meta(self):
        lead = Lead.objects.create(
            id=uuid.uuid4(),
            tenant=self.tenant,
            chatbot=self.bot,
            conversation=self.convo,
            name="",
            primary_email="",
            phone="",
        )

        Message.objects.create(
            id=uuid.uuid4(),
            tenant=self.tenant,
            conversation=self.convo,
            role=Message.Role.USER,
            content="Hi, what are your pricing plans? I want a demo ASAP.",
        )

        # Call task synchronously in test
        enrich_conversation_signals(str(self.tenant.id), str(self.convo.id))

        self.convo.refresh_from_db()
        lead.refresh_from_db()

        self.assertIn("signals", self.convo.meta_json)
        self.assertIn("signals", lead.meta_json)

        sig = lead.meta_json["signals"]
        self.assertIn("pricing", sig.get("topics", {}))
        self.assertIn("demo_intent", sig.get("intents", {}))
        self.assertIn("urgent", sig.get("intents", {}))
        self.assertGreaterEqual(int(sig.get("score", 0)), 30)
