from django.urls import path

from core.api_keys.views import (
    ChatbotApiKeysView,
    ApiKeyRotateView,
    ApiKeyRevokeView,
)

urlpatterns = [
    # list + create (same path, method-based)
    path("chatbots/<uuid:chatbot_id>/api-keys", ChatbotApiKeysView.as_view(), name="chatbot-api-keys"),

    # rotate / revoke
    path("api-keys/<uuid:api_key_id>/rotate", ApiKeyRotateView.as_view(), name="api-key-rotate"),
    path("api-keys/<uuid:api_key_id>/revoke", ApiKeyRevokeView.as_view(), name="api-key-revoke"),
]
