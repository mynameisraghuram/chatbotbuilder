from celery import shared_task
from django.db import transaction
from django.utils import timezone

from core.knowledge.models import IngestionJob, KnowledgeSource
from core.knowledge.extractors import (
    extract_from_text,
    extract_from_url,
    extract_from_pdf_file,
    chunk_text,
)
from core.knowledge.opensearch import bulk_index_chunks, delete_by_source


@shared_task(name="core.knowledge.tasks.ingestion_run")
def ingestion_run(job_id: str) -> str:
    job = IngestionJob.objects.select_related("source").get(id=job_id)

    # Tenant safety: never process inactive source
    if not job.source.is_active:
        job.status = IngestionJob.Status.FAILED
        job.error_code = "SOURCE_INACTIVE"
        job.error_message = "Source is inactive"
        job.finished_at = timezone.now()
        job.save(update_fields=["status", "error_code", "error_message", "finished_at", "updated_at"])
        return "failed"

    # Mark running (idempotent)
    with transaction.atomic():
        job = IngestionJob.objects.select_for_update().get(id=job_id)
        if job.status == IngestionJob.Status.SUCCEEDED:
            return "already_succeeded"
        job.status = IngestionJob.Status.RUNNING
        job.attempts += 1
        job.started_at = job.started_at or timezone.now()
        job.error_code = ""
        job.error_message = ""
        job.save(update_fields=["status", "attempts", "started_at", "error_code", "error_message", "updated_at"])

    try:
        src: KnowledgeSource = job.source

        # Clean old docs for this source (idempotent re-index)
        delete_by_source(tenant_id=job.tenant_id, source_id=src.id)

        # Extract
        if src.source_type == KnowledgeSource.SourceType.TEXT:
            text = extract_from_text(src.input_text)

        elif src.source_type == KnowledgeSource.SourceType.URL:
            text = extract_from_url(src.input_url)

        elif src.source_type == KnowledgeSource.SourceType.FILE:
            if not src.input_file:
                raise ValueError("Missing file")
            path = src.input_file.path
            if path.lower().endswith(".pdf"):
                text = extract_from_pdf_file(path)
            else:
                # fallback: treat as utf-8 text
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    text = f.read()

        else:
            raise ValueError(f"Unsupported source_type: {src.source_type}")

        chunks = chunk_text(text)
        indexed = bulk_index_chunks(
            tenant_id=str(job.tenant_id),
            source_id=str(src.id),
            title=src.title,
            chunks=chunks,
        )

        job.status = IngestionJob.Status.SUCCEEDED
        job.finished_at = timezone.now()
        job.save(update_fields=["status", "finished_at", "updated_at"])
        return f"succeeded:indexed={indexed}"

    except Exception as e:
        job.status = IngestionJob.Status.FAILED
        job.error_code = "INGESTION_FAILED"
        job.error_message = str(e)
        job.finished_at = timezone.now()
        job.save(update_fields=["status", "error_code", "error_message", "finished_at", "updated_at"])
        raise
