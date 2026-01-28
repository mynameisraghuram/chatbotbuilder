from django.urls import path

from core.webhooks.api import (
    webhook_endpoints,
    webhook_endpoint_detail,
    webhook_endpoint_rotate_secret,
)

urlpatterns = [
    path("webhooks/endpoints", webhook_endpoints, name="webhook-endpoints"),
    path("webhooks/endpoints/<uuid:endpoint_id>", webhook_endpoint_detail, name="webhook-endpoint-detail"),
    path("webhooks/endpoints/<uuid:endpoint_id>/rotate-secret", webhook_endpoint_rotate_secret, name="webhook-endpoint-rotate-secret"),
]
