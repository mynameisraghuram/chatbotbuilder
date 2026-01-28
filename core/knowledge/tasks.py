# repo-root/backend/core/knowledge/tasks.py
from celery import shared_task
from django.db import transaction
from django.utils import timezone

from core.knowledge.models import IngestionJob, KnowledgeSource
from core.knowledge.extractors import (
    extract_from_text,
    extract_from_url,
    extract_from_pdf_bytes,
    extract_from_docx_bytes,
    extract_from_plaintext_bytes,
    chunk_text,
)
from core.knowledge.opensearch import bulk_index_chunks, delete_by_source


def _set_progress(job: IngestionJob, stage: str, pct: int):
    job.stage = stage
    job.progress_percent = max(0, min(100, int(pct)))
    job.save(update_fields=["stage", "progress_percent", "updated_at"])


@shared_task(name="core.knowledge.tasks.ingestion_run")
def ingestion_run(job_id: str) -> str:
    job = IngestionJob.objects.select_related("source").get(id=job_id)

    if not job.source.is_active:
        job.status = IngestionJob.Status.FAILED
        job.stage = IngestionJob.Stage.FAILED
        job.progress_percent = 0
        job.error_code = "SOURCE_INACTIVE"
        job.error_message = "Source is inactive"
        job.last_error_at = timezone.now()
        job.finished_at = timezone.now()
        job.save(update_fields=[
            "status", "stage", "progress_percent",
            "error_code", "error_message", "last_error_at",
            "finished_at", "updated_at"
        ])
        return "failed"

    # mark running (idempotent)
    with transaction.atomic():
        job = IngestionJob.objects.select_for_update().get(id=job_id)
        if job.status == IngestionJob.Status.SUCCEEDED:
            return "already_succeeded"
        job.status = IngestionJob.Status.RUNNING
        job.attempts += 1
        job.started_at = job.started_at or timezone.now()
        job.error_code = ""
        job.error_message = ""
        job.stage = IngestionJob.Stage.QUEUED
        job.progress_percent = 0
        job.save(update_fields=[
            "status", "attempts", "started_at",
            "error_code", "error_message",
            "stage", "progress_percent",
            "updated_at"
        ])

    try:
        src: KnowledgeSource = job.source

        _set_progress(job, IngestionJob.Stage.CLEANUP, 5)
        delete_by_source(tenant_id=str(job.tenant_id), source_id=str(src.id))

        # Extract
        _set_progress(job, IngestionJob.Stage.EXTRACT, 20)

        if src.source_type == KnowledgeSource.SourceType.TEXT:
            text = extract_from_text(src.input_text)

        elif src.source_type == KnowledgeSource.SourceType.URL:
            text = extract_from_url(src.input_url)

        elif src.source_type == KnowledgeSource.SourceType.FILE:
            if not src.input_file:
                raise ValueError("Missing file")

            # Works with S3/local storage (no .path)
            src.input_file.open("rb")
            data = src.input_file.read()
            src.input_file.close()

            name = (src.input_file.name or "").lower()

            if name.endswith(".pdf"):
                text = extract_from_pdf_bytes(data)
            elif name.endswith(".docx"):
                text = extract_from_docx_bytes(data)
            else:
                text = extract_from_plaintext_bytes(data)

        else:
            raise ValueError(f"Unsupported source_type: {src.source_type}")

        _set_progress(job, IngestionJob.Stage.CHUNK, 55)
        chunks = chunk_text(text)

        _set_progress(job, IngestionJob.Stage.INDEX, 80)
        indexed = bulk_index_chunks(
            tenant_id=str(job.tenant_id),
            source_id=str(src.id),
            title=src.title,
            chunks=chunks,
        )

        job.status = IngestionJob.Status.SUCCEEDED
        job.stage = IngestionJob.Stage.DONE
        job.progress_percent = 100
        job.finished_at = timezone.now()
        job.save(update_fields=["status", "stage", "progress_percent", "finished_at", "updated_at"])
        return f"succeeded:indexed={indexed}"

    except Exception as e:
        job.status = IngestionJob.Status.FAILED
        job.stage = IngestionJob.Stage.FAILED
        job.progress_percent = 0
        job.error_code = "INGESTION_FAILED"
        job.error_message = str(e)
        job.last_error_at = timezone.now()
        job.finished_at = timezone.now()
        job.save(update_fields=[
            "status", "stage", "progress_percent",
            "error_code", "error_message", "last_error_at",
            "finished_at", "updated_at"
        ])
        raise
