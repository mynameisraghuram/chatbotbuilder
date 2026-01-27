from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

from core.knowledge.models import KnowledgeSource, IngestionJob
from core.knowledge.serializers import KnowledgeSourceSerializer, IngestionJobSerializer
from core.knowledge.tasks import ingestion_run


def get_tenant_id_from_request(request) -> str:
    # Assumption: you already enforce tenant headers/middleware in your project.
    # If not, we’ll standardize it next. For now we read header.
    tenant_id = request.headers.get("X-Tenant-Id") or request.headers.get("x-tenant-id")
    if not tenant_id:
        return ""
    return tenant_id


class KnowledgeSourceViewSet(viewsets.ModelViewSet):
    serializer_class = KnowledgeSourceSerializer
    queryset = KnowledgeSource.objects.all()

    def get_queryset(self):
        tenant_id = get_tenant_id_from_request(self.request)
        return KnowledgeSource.objects.filter(tenant_id=tenant_id, is_active=True).order_by("-created_at")

    def perform_create(self, serializer):
        tenant_id = get_tenant_id_from_request(self.request)
        serializer.save(tenant_id=tenant_id)

    @action(detail=True, methods=["post"], url_path="ingest")
    def ingest(self, request, pk=None):
        tenant_id = get_tenant_id_from_request(request)
        source = self.get_queryset().get(id=pk)

        idem = (request.data or {}).get("idempotency_key", "") or ""

        job, created = IngestionJob.objects.get_or_create(
            tenant_id=tenant_id,
            source=source,
            idempotency_key=idem,
            defaults={"status": IngestionJob.Status.QUEUED},
        )

        # If already succeeded and same idem key => return same job
        if job.status == IngestionJob.Status.SUCCEEDED:
            return Response(IngestionJobSerializer(job).data, status=status.HTTP_200_OK)

        # Queue the task (idempotent)
        ingestion_run.delay(str(job.id))

        return Response(IngestionJobSerializer(job).data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    def perform_destroy(self, instance):
        # Soft delete for now: mark inactive (keeps auditability)
        instance.is_active = False
        instance.save(update_fields=["is_active", "updated_at"])


class IngestionJobViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = IngestionJobSerializer
    queryset = IngestionJob.objects.all()

    def get_queryset(self):
        tenant_id = get_tenant_id_from_request(self.request)
        return IngestionJob.objects.filter(tenant_id=tenant_id).order_by("-created_at")

    @action(detail=True, methods=["post"], url_path="reprocess")
    def reprocess(self, request, pk=None):
        tenant_id = get_tenant_id_from_request(request)
        job = self.get_queryset().get(id=pk)

        # Create a new job if caller supplies a new idempotency key, else reuse
        idem = (request.data or {}).get("idempotency_key", "") or job.idempotency_key or ""

        new_job, _ = IngestionJob.objects.get_or_create(
            tenant_id=tenant_id,
            source=job.source,
            idempotency_key=idem,
            defaults={"status": IngestionJob.Status.QUEUED},
        )

        ingestion_run.delay(str(new_job.id))
        return Response(IngestionJobSerializer(new_job).data, status=status.HTTP_200_OK)
