# backend/core/chatbots/management/commands/run_test_public_chat_setup.py

import secrets

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

from core.tenants.models import Tenant
from core.iam.models import TenantMembership
from core.chatbots.models import Chatbot
from core.api_keys.models import ApiKey
from core.api_keys.utils import hash_key


class Command(BaseCommand):
    help = "Idempotently create/get a test chatbot and create a public API key for public chat testing"

    def handle(self, *args, **options):
        self.stdout.write("Setting up public chat test data...")

        User = get_user_model()

        tenant = Tenant.objects.order_by("-created_at").first()
        if not tenant:
            self.stderr.write("No tenant found. Run: python manage.py run_test_ingestion")
            return

        # User (idempotent)
        user, created = User.objects.get_or_create(
            username="public_chat_owner",
            defaults={"email": "owner@acme.com"},
        )
        if created:
            user.set_password("Test@12345")
            user.save(update_fields=["password"])

        # Membership (idempotent) - role is plain string in your project
        TenantMembership.objects.get_or_create(
            tenant=tenant,
            user=user,
            defaults={"role": "owner"},
        )

        # Chatbot (idempotent) - avoids uq_chatbot_tenant_name violation
        bot, _ = Chatbot.objects.get_or_create(
            tenant=tenant,
            name="Acme Public Bot",
            defaults={"citations_enabled": True},
        )

        # Always create a NEW api key so you can test multiple keys easily
        raw_key = "cb_live_" + secrets.token_urlsafe(32)

        fields = {f.name for f in ApiKey._meta.get_fields()}
        create_kwargs = {
            "tenant": tenant,
            "chatbot": bot,
            "key_hash": hash_key(raw_key),
        }

        if "status" in fields:
            create_kwargs["status"] = ApiKey.Status.ACTIVE

        if "rate_limit_per_min" in fields:
            create_kwargs["rate_limit_per_min"] = 60
        elif "rate_limit" in fields:
            create_kwargs["rate_limit"] = 60

        if "name" in fields:
            create_kwargs["name"] = "Public Widget Key"
        elif "label" in fields:
            create_kwargs["label"] = "Public Widget Key"

        ApiKey.objects.create(**create_kwargs)

        self.stdout.write(self.style.SUCCESS("Public chat setup complete"))
        self.stdout.write(f"X-Chatbot-Key: {raw_key}")
        self.stdout.write(f"Tenant ID: {tenant.id}")
        self.stdout.write(f"Chatbot ID: {bot.id}")
