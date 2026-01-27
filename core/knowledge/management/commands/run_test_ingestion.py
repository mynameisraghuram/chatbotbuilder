# backend/core/knowledge/management/commands/run_test_ingestion.py

from django.core.management.base import BaseCommand

from core.tenants.models import Tenant
from core.knowledge.models import KnowledgeSource, IngestionJob
from core.knowledge.tasks import ingestion_run


class Command(BaseCommand):
    help = "Run a test ingestion job and index chunks into OpenSearch"

    def handle(self, *args, **options):
        self.stdout.write("Starting test ingestion...")

        # 1) Create or reuse tenant
        tenant, _ = Tenant.objects.get_or_create(name="KB Test Tenant")

        # 2) Create TEXT knowledge source
        src = KnowledgeSource.objects.create(
            tenant=tenant,
            source_type=KnowledgeSource.SourceType.TEXT,
            title="Refund Policy",
            input_text=(
                "Refund policy: refunds are allowed within 7 days with invoice. "
                "Support is available 24/7."
            ),
        )

        # 3) Create ingestion job (do NOT force a status; use model default)
        job = IngestionJob.objects.create(
            tenant=tenant,
            source=src,
        )

        # 4) Run ingestion synchronously (no Celery needed)
        result = ingestion_run(str(job.id))

        # 5) Reload job
        job.refresh_from_db()

        self.stdout.write(self.style.SUCCESS(f"Ingestion result: {result}"))
        self.stdout.write(
            f"Status={job.status}, Stage={job.stage}, Error={job.error_code or 'NONE'}"
        )
