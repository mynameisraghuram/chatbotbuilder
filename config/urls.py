# repo-root/backend/config/urls.py

from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from core.common.views import health_check

urlpatterns = [
    # 🔹 Root → API docs (prevents confusing 404 on refresh)
    path("", lambda request: redirect("/api/docs/")),

    path("admin/", admin.site.urls),

    # simple non-tenant health (not under /v1)
    path("health/", health_check, name="health-check"),

    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),

    path("v1/auth/login", TokenObtainPairView.as_view(), name="jwt-login"),
    path("v1/auth/refresh", TokenRefreshView.as_view(), name="jwt-refresh"),

    # ✅ tenantless health endpoint under v1
    path("v1/health/", include("core.common.urls_health")),

    path("v1/", include("core.tenants.urls")),
    path("v1/", include("core.flags.urls")),
    path("v1/", include("core.iam.urls")),
    path("v1/", include("core.search.urls")),
    path("v1/", include("core.knowledge.urls")),
    path("v1/", include("core.chatbots.urls")),
    path("v1/", include("core.api_keys.urls")),
    path("v1/", include("core.public.urls")),
    path("v1/", include("core.leads.urls")),
    path("v1/", include("core.analytics.urls")),
    path("v1/", include("core.conversations.urls")),
    path("v1/", include("core.webhooks.urls")),
    path("v1/", include("core.notifications.urls")),
    path("v1/", include("core.audit.urls")),
]
