from core.knowledge.models import IngestionJob


def tenant_knowledge_ready(*, tenant_id) -> bool:
    """
    Returns True if tenant has at least one succeeded ingestion job.
    """
    return IngestionJob.objects.filter(
        tenant_id=tenant_id,
        status=IngestionJob.Status.SUCCEEDED,
    ).exists()
