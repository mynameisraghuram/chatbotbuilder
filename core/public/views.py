import time
from django.db import transaction
from django.utils import timezone

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from core.api_keys.public_auth import ChatbotKeyAuthentication
from core.common.ratelimit import rate_limit_or_raise, RateLimitExceeded
from core.public.serializers import PublicChatRequestSerializer

from core.chatbots.models import Chatbot
from core.conversations.models import Conversation, Message


def _rate_limit(request):
    tenant_id = str(getattr(request, "public_tenant_id", ""))
    chatbot_id = str(getattr(request, "public_chatbot_id", ""))
    api_key_id = str(getattr(request, "public_api_key_id", ""))
    limit = int(getattr(request, "public_rate_limit_per_min", 60))

    minute_bucket = int(time.time() // 60)
    rl_key = f"rl:{tenant_id}:{chatbot_id}:{api_key_id}:{minute_bucket}"

    try:
        rate_limit_or_raise(key=rl_key, limit=limit, window_seconds=60)
    except RateLimitExceeded as e:
        return Response(
            {
                "error": {
                    "code": "RATE_LIMITED",
                    "message": "Too many requests",
                    "details": {"retry_after": e.retry_after_seconds},
                }
            },
            status=status.HTTP_429_TOO_MANY_REQUESTS,
            headers={"Retry-After": str(e.retry_after_seconds)},
        )
    return None


class PublicPingView(APIView):
    authentication_classes = [ChatbotKeyAuthentication]
    permission_classes = []

    def get(self, request):
        rl = _rate_limit(request)
        if rl:
            return rl

        return Response(
            {
                "ok": True,
                "tenant_id": str(getattr(request, "public_tenant_id", "")),
                "chatbot_id": str(getattr(request, "public_chatbot_id", "")),
                "api_key_id": str(getattr(request, "public_api_key_id", "")),
                "rate_limit_per_min": int(getattr(request, "public_rate_limit_per_min", 60)),
            },
            status=200,
        )


class PublicChatView(APIView):
    """
    POST /v1/public/chat
    Headers:
      X-Chatbot-Key: <raw_key>

    Body:
      {
        "conversation_id": "<uuid optional>",
        "message": "hello",
        "external_user_id": "... optional",
        "session_id": "... optional",
        "user_email": "... optional",
        "meta": {... optional }
      }
    """
    authentication_classes = [ChatbotKeyAuthentication]
    permission_classes = []

    def post(self, request):
        rl = _rate_limit(request)
        if rl:
            return rl

        s = PublicChatRequestSerializer(data=request.data)
        s.is_valid(raise_exception=True)

        tenant_id = getattr(request, "public_tenant_id")
        chatbot_id = getattr(request, "public_chatbot_id")

        # Ensure chatbot exists and is active (avoid leaking)
        bot = Chatbot.objects.filter(id=chatbot_id, tenant_id=tenant_id, deleted_at__isnull=True).first()
        if not bot or bot.status != Chatbot.Status.ACTIVE:
            return Response(
                {"error": {"code": "NOT_FOUND", "message": "Chatbot not found", "details": {}}},
                status=status.HTTP_404_NOT_FOUND,
            )

        data = s.validated_data
        user_message = data["message"].strip()
        if not user_message:
            return Response(
                {"error": {"code": "VALIDATION_ERROR", "message": "message cannot be empty", "details": {}}},
                status=422,
            )

        # Create or load conversation strictly within tenant+chatbot
        with transaction.atomic():
            conv = None
            conv_id = data.get("conversation_id")

            if conv_id:
                conv = Conversation.objects.select_for_update().filter(
                    id=conv_id, tenant_id=tenant_id, chatbot_id=chatbot_id
                ).first()

            if not conv:
                conv = Conversation.objects.create(
                    tenant_id=tenant_id,
                    chatbot_id=chatbot_id,
                    external_user_id=data.get("external_user_id", "") or "",
                    session_id=data.get("session_id", "") or "",
                    user_email=data.get("user_email", "") or "",
                    meta_json=data.get("meta", {}) or {},
                )

            # Store user message
            Message.objects.create(
                tenant_id=tenant_id,
                conversation=conv,
                role=Message.Role.USER,
                content=user_message,
                meta_json={"ts": timezone.now().isoformat()},
            )

            # Placeholder assistant reply (we’ll replace with retrieval + generation later)
            assistant_text = "Thanks! I’ve received your message. (Next step: connect knowledge search + response.)"

            Message.objects.create(
                tenant_id=tenant_id,
                conversation=conv,
                role=Message.Role.ASSISTANT,
                content=assistant_text,
                meta_json={"placeholder": True},
            )

            conv.updated_at = timezone.now()
            conv.save(update_fields=["updated_at"])

        return Response(
            {
                "conversation_id": str(conv.id),
                "reply": assistant_text,
            },
            status=status.HTTP_200_OK,
        )
