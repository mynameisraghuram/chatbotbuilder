#backend/core/common/urls_health.py
from django.urls import path

from core.common.api_health import health

urlpatterns = [
    path("", health),
]
