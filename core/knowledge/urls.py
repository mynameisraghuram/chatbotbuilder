from django.urls import path, include
from rest_framework.routers import DefaultRouter

from core.knowledge.views import (
    KnowledgeSourceViewSet,
    IngestionJobViewSet,
    knowledge_source_create_contract,
    knowledge_source_files_contract,
    knowledge_ingestion_status,
    knowledge_reprocess_contract,
)

router = DefaultRouter()
# existing/backward-compatible
router.register(r"knowledge/sources", KnowledgeSourceViewSet, basename="knowledge-source")
router.register(r"knowledge/jobs", IngestionJobViewSet, basename="knowledge-job")

urlpatterns = [
    path("", include(router.urls)),

    # contract-style endpoints
    path("knowledge-sources", knowledge_source_create_contract, name="knowledge-sources-create"),
    path("knowledge-sources/files", knowledge_source_files_contract, name="knowledge-sources-files"),
    path("knowledge-sources/<uuid:source_id>/ingestion", knowledge_ingestion_status, name="knowledge-sources-ingestion"),
    path("knowledge-sources/<uuid:source_id>/reprocess", knowledge_reprocess_contract, name="knowledge-sources-reprocess"),
]
