# backend/core/public/management/commands/run_test_public_chat.py

import json
import secrets
from django.core.management.base import BaseCommand
from rest_framework.test import APIClient

from core.tenants.models import Tenant
from core.chatbots.models import Chatbot
from core.api_keys.models import ApiKey
from core.api_keys.utils import hash_key


class Command(BaseCommand):
    help = "Local smoke test for /v1/public/chat (auth + routing + persistence)"

    def handle(self, *args, **options):
        self.stdout.write("Running public chat smoke test...")

        tenant = Tenant.objects.create(name="Smoke Tenant")

        bot = Chatbot.objects.create(
            tenant=tenant,
            name="Smoke Bot",
            citations_enabled=True,
            status=Chatbot.Status.ACTIVE,
        )

        raw_key = "cb_live_" + secrets.token_urlsafe(24)

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

        ApiKey.objects.create(**create_kwargs)

        client = APIClient()
        resp = client.post(
            "/v1/public/chat",
            {"message": "refund policy"},
            format="json",
            HTTP_X_CHATBOT_KEY=raw_key,
        )

        self.stdout.write(f"HTTP {resp.status_code}")

        try:
            self.stdout.write(json.dumps(resp.json(), indent=2))
        except Exception:
            self.stdout.write(resp.content.decode("utf-8", errors="ignore"))
