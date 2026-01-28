from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

from core.api_keys.models import ApiKey
from core.api_keys.utils import hash_key


class ChatbotKeyAuthentication(BaseAuthentication):
    """
    Header:
      X-Chatbot-Key: <raw key>

    On success sets:
      request.public_tenant_id
      request.public_chatbot_id
      request.public_api_key_id
      request.public_rate_limit_per_min
    """

    def authenticate(self, request):
        raw = request.META.get("HTTP_X_CHATBOT_KEY")
        if not raw:
            return None

        key_hash = hash_key(raw)
        row = (
            ApiKey.objects.select_related("tenant", "chatbot")
            .filter(key_hash=key_hash, status=ApiKey.Status.ACTIVE)
            .first()
        )
        if not row:
            raise AuthenticationFailed("Invalid or revoked chatbot key.")

        row.mark_used()

        request.public_tenant_id = row.tenant_id
        request.public_chatbot_id = row.chatbot_id
        request.public_api_key_id = row.id
        request.public_rate_limit_per_min = int(getattr(row, "rate_limit_per_min", 60) or 60)

        # Public endpoints do not map to a Django user
        return (None, row)
