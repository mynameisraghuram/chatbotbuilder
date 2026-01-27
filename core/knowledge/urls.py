from django.urls import path, include
from rest_framework.routers import DefaultRouter
from core.knowledge.views import KnowledgeSourceViewSet, IngestionJobViewSet

router = DefaultRouter()
router.register(r"knowledge/sources", KnowledgeSourceViewSet, basename="knowledge-source")
router.register(r"knowledge/jobs", IngestionJobViewSet, basename="knowledge-job")

urlpatterns = [
    path("", include(router.urls)),
]
