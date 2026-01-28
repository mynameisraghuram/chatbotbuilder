from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.knowledge.models import KnowledgeSource, IngestionJob
from core.knowledge.serializers import (
    KnowledgeSourceSerializer,
    KnowledgeSourceCreateSerializer,
    IngestionJobSerializer,
)
from core.knowledge.tasks import ingestion_run


def _tenant_id(request):
    # middleware already attaches UUID
    return getattr(request, "tenant_id", None)


class KnowledgeSourceViewSet(viewsets.ModelViewSet):
    """
    Backward-compatible existing route:
      /v1/knowledge/sources
    """
    serializer_class = KnowledgeSourceSerializer
    queryset = KnowledgeSource.objects.all()
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return KnowledgeSource.objects.filter(tenant_id=_tenant_id(self.request), is_active=True).order_by("-created_at")

    def perform_create(self, serializer):
        serializer.save(tenant_id=_tenant_id(self.request))

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save(update_fields=["is_active", "updated_at"])

    @action(detail=True, methods=["post"], url_path="ingest")
    def ingest(self, request, pk=None):
        source = self.get_queryset().get(id=pk)
        idem = request.headers.get("Idempotency-Key", "") or ""

        job, created = IngestionJob.objects.get_or_create(
            tenant_id=_tenant_id(request),
            source=source,
            idempotency_key=idem,
            defaults={"status": IngestionJob.Status.QUEUED, "stage": IngestionJob.Stage.QUEUED, "progress_percent": 0},
        )

        if job.status == IngestionJob.Status.SUCCEEDED:
            return Response(IngestionJobSerializer(job).data, status=status.HTTP_200_OK)

        ingestion_run.delay(str(job.id))
        return Response(IngestionJobSerializer(job).data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class IngestionJobViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Backward-compatible existing route:
      /v1/knowledge/jobs
    """
    serializer_class = IngestionJobSerializer
    queryset = IngestionJob.objects.all()
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return IngestionJob.objects.filter(tenant_id=_tenant_id(self.request)).order_by("-created_at")


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def knowledge_source_create_contract(request):
    """
    POST /v1/knowledge-sources
    For URL/TEXT sources.
    """
    s = KnowledgeSourceCreateSerializer(data=request.data)
    s.is_valid(raise_exception=True)

    src = KnowledgeSource.objects.create(
        tenant_id=_tenant_id(request),
        source_type=s.validated_data["source_type"],
        title=s.validated_data.get("title", "") or "",
        input_text=s.validated_data.get("input_text", "") or "",
        input_url=s.validated_data.get("input_url", "") or "",
    )

    # auto-queue ingestion (optional MVP behavior)
    idem = request.headers.get("Idempotency-Key", "") or ""
    job, _ = IngestionJob.objects.get_or_create(
        tenant_id=_tenant_id(request),
        source=src,
        idempotency_key=idem,
        defaults={"status": IngestionJob.Status.QUEUED, "stage": IngestionJob.Stage.QUEUED, "progress_percent": 0},
    )
    ingestion_run.delay(str(job.id))

    return Response(
        {
            "knowledge_source": KnowledgeSourceSerializer(src).data,
            "ingestion_job": IngestionJobSerializer(job).data,
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def knowledge_source_files_contract(request):
    """
    POST /v1/knowledge-sources/files  (multipart)
    Supports multiple files in one request: files[]
    """
    tenant_id = _tenant_id(request)
    files = request.FILES.getlist("files")
    title = request.data.get("title", "") or ""

    if not files:
        return Response(
            {"error": {"code": "VALIDATION_ERROR", "message": "files[] is required", "details": {}}},
            status=422,
        )

    items = []
    for f in files:
        src = KnowledgeSource.objects.create(
            tenant_id=tenant_id,
            source_type=KnowledgeSource.SourceType.FILE,
            title=title or f.name,
            input_file=f,
        )

        idem = request.headers.get("Idempotency-Key", "") or ""
        job, _ = IngestionJob.objects.get_or_create(
            tenant_id=tenant_id,
            source=src,
            idempotency_key=idem,
            defaults={"status": IngestionJob.Status.QUEUED, "stage": IngestionJob.Stage.QUEUED, "progress_percent": 0},
        )
        ingestion_run.delay(str(job.id))

        items.append({"knowledge_source": KnowledgeSourceSerializer(src).data, "ingestion_job": IngestionJobSerializer(job).data})

    return Response({"items": items}, status=status.HTTP_201_CREATED)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def knowledge_ingestion_status(request, source_id):
    """
    GET /v1/knowledge-sources/{id}/ingestion
    """
    tenant_id = _tenant_id(request)
    src = KnowledgeSource.objects.filter(tenant_id=tenant_id, id=source_id, is_active=True).first()
    if not src:
        return Response({"error": {"code": "NOT_FOUND", "message": "Knowledge source not found", "details": {}}}, status=404)

    job = IngestionJob.objects.filter(tenant_id=tenant_id, source=src).order_by("-created_at").first()
    if not job:
        return Response({"knowledge_source_id": str(src.id), "status": "pending", "progress": {"stage": "queued", "percent": 0, "message": "Not started"}}, status=200)

    return Response(
        {
            "knowledge_source_id": str(src.id),
            "status": job.status,
            "progress": {
                "stage": job.stage,
                "percent": job.progress_percent,
                "message": job.error_message if job.status == IngestionJob.Status.FAILED else job.stage,
            },
            "last_error": None if job.status != IngestionJob.Status.FAILED else {"code": job.error_code, "message": job.error_message},
            "started_at": job.started_at,
            "updated_at": job.updated_at,
        },
        status=200,
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def knowledge_reprocess_contract(request, source_id):
    """
    POST /v1/knowledge-sources/{id}/reprocess
    Idempotency-Key is REQUIRED.
    """
    tenant_id = _tenant_id(request)
    src = KnowledgeSource.objects.filter(tenant_id=tenant_id, id=source_id, is_active=True).first()
    if not src:
        return Response({"error": {"code": "NOT_FOUND", "message": "Knowledge source not found", "details": {}}}, status=404)

    idem = request.headers.get("Idempotency-Key", "") or ""
    if not idem:
        return Response(
            {"error": {"code": "VALIDATION_ERROR", "message": "Idempotency-Key header is required", "details": {}}},
            status=422,
        )

    job, created = IngestionJob.objects.get_or_create(
        tenant_id=tenant_id,
        source=src,
        idempotency_key=idem,
        defaults={"status": IngestionJob.Status.QUEUED, "stage": IngestionJob.Stage.QUEUED, "progress_percent": 0},
    )

    # replay behavior
    if not created and job.status in (IngestionJob.Status.QUEUED, IngestionJob.Status.RUNNING, IngestionJob.Status.SUCCEEDED):
        return Response(IngestionJobSerializer(job).data, status=status.HTTP_200_OK)

    ingestion_run.delay(str(job.id))
    return Response(IngestionJobSerializer(job).data, status=status.HTTP_202_ACCEPTED)
