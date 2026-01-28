import uuid
from django.db import models
from django.utils import timezone

from core.tenants.models import Tenant


class KnowledgeSource(models.Model):
    class SourceType(models.TextChoices):
        TEXT = "text", "Text"
        URL = "url", "URL"
        FILE = "file", "File"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="knowledge_sources")

    source_type = models.CharField(max_length=16, choices=SourceType.choices)
    title = models.CharField(max_length=255, blank=True, default="")

    input_text = models.TextField(blank=True, default="")
    input_url = models.URLField(blank=True, default="")
    input_file = models.FileField(upload_to="knowledge/", blank=True, null=True)

    # keep existing soft-delete mechanism
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "knowledge_source"
        indexes = [
            models.Index(fields=["tenant", "created_at"]),
            models.Index(fields=["tenant", "source_type"]),
        ]

    def __str__(self) -> str:
        return f"{self.tenant_id}::{self.source_type}::{self.title or self.id}"


class IngestionJob(models.Model):
    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        RUNNING = "running", "Running"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"

    class Stage(models.TextChoices):
        QUEUED = "queued", "Queued"
        CLEANUP = "cleanup", "Cleanup"
        EXTRACT = "extract", "Extract"
        CHUNK = "chunk", "Chunk"
        INDEX = "index", "Index"
        DONE = "done", "Done"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="ingestion_jobs")
    source = models.ForeignKey(KnowledgeSource, on_delete=models.CASCADE, related_name="ingestion_jobs")

    # Idempotency key: same (tenant, source, key) => same job
    idempotency_key = models.CharField(max_length=80, blank=True, default="")

    status = models.CharField(max_length=16, choices=Status.choices, default=Status.QUEUED)

    # progress / observability
    stage = models.CharField(max_length=16, choices=Stage.choices, default=Stage.QUEUED)
    progress_percent = models.PositiveSmallIntegerField(default=0)

    attempts = models.PositiveIntegerField(default=0)

    error_code = models.CharField(max_length=64, blank=True, default="")
    error_message = models.TextField(blank=True, default="")
    last_error_at = models.DateTimeField(blank=True, null=True)

    started_at = models.DateTimeField(blank=True, null=True)
    finished_at = models.DateTimeField(blank=True, null=True)

    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "knowledge_ingestion_job"
        indexes = [
            models.Index(fields=["tenant", "created_at"]),
            models.Index(fields=["tenant", "status"]),
            models.Index(fields=["source", "created_at"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "source", "idempotency_key"],
                name="uq_ingestion_idempotency",
                condition=~models.Q(idempotency_key=""),
            )
        ]
