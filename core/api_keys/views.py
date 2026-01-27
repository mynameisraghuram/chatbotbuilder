from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from core.api_keys.models import ApiKey
from core.api_keys.serializers import ApiKeySerializer
from core.api_keys.utils import generate_raw_key, key_prefix, hash_key
from core.chatbots.models import Chatbot
from core.iam.permissions import IsTenantMember


def _tenant_id(request):
    return getattr(request, "tenant_id", None)


def _is_owner_or_admin(request) -> bool:
    return getattr(request, "tenant_role", None) in ("owner", "admin")


class ChatbotApiKeysView(APIView):
    """
    GET  /v1/chatbots/<chatbot_id>/api-keys
    POST /v1/chatbots/<chatbot_id>/api-keys
    """
    permission_classes = [IsAuthenticated, IsTenantMember]

    def get(self, request, chatbot_id):
        tenant_id = _tenant_id(request)
        bot = Chatbot.objects.filter(
            id=chatbot_id, tenant_id=tenant_id, deleted_at__isnull=True
        ).first()
        if not bot:
            return Response(
                {"error": {"code": "NOT_FOUND", "message": "Chatbot not found", "details": {}}},
                status=status.HTTP_404_NOT_FOUND,
            )

        qs = ApiKey.objects.filter(tenant_id=tenant_id, chatbot_id=bot.id).order_by("-created_at")
        return Response({"items": ApiKeySerializer(qs, many=True).data}, status=status.HTTP_200_OK)

    def post(self, request, chatbot_id):
        if not _is_owner_or_admin(request):
            return Response(
                {"error": {"code": "FORBIDDEN", "message": "Only owner/admin can manage API keys", "details": {}}},
                status=status.HTTP_403_FORBIDDEN,
            )

        tenant_id = _tenant_id(request)
        bot = Chatbot.objects.filter(
            id=chatbot_id, tenant_id=tenant_id, deleted_at__isnull=True
        ).first()
        if not bot:
            return Response(
                {"error": {"code": "NOT_FOUND", "message": "Chatbot not found", "details": {}}},
                status=status.HTTP_404_NOT_FOUND,
            )

        # optional request field
        rate = request.data.get("rate_limit_per_min", 60)
        try:
            rate = int(rate)
        except Exception:
            rate = 60
        rate = max(1, min(rate, 600))

        raw = generate_raw_key()
        row = ApiKey.objects.create(
            tenant_id=tenant_id,
            chatbot_id=bot.id,
            key_prefix=key_prefix(raw),
            key_hash=hash_key(raw),
            status=ApiKey.Status.ACTIVE,
            rate_limit_per_min=rate,
        )

        # raw key returned only once
        return Response(
            {"api_key": {**ApiKeySerializer(row).data, "raw_key": raw}},
            status=status.HTTP_201_CREATED,
        )


class ApiKeyRevokeView(APIView):
    """
    POST /v1/api-keys/<api_key_id>/revoke
    """
    permission_classes = [IsAuthenticated, IsTenantMember]

    def post(self, request, api_key_id):
        if not _is_owner_or_admin(request):
            return Response(
                {"error": {"code": "FORBIDDEN", "message": "Only owner/admin can manage API keys", "details": {}}},
                status=status.HTTP_403_FORBIDDEN,
            )

        tenant_id = _tenant_id(request)
        row = ApiKey.objects.filter(id=api_key_id, tenant_id=tenant_id).first()
        if not row:
            return Response(
                {"error": {"code": "NOT_FOUND", "message": "API key not found", "details": {}}},
                status=status.HTTP_404_NOT_FOUND,
            )

        # idempotent revoke
        row.revoke()
        return Response({"api_key": ApiKeySerializer(row).data}, status=status.HTTP_200_OK)


class ApiKeyRotateView(APIView):
    """
    POST /v1/api-keys/<api_key_id>/rotate
    """
    permission_classes = [IsAuthenticated, IsTenantMember]

    def post(self, request, api_key_id):
        if not _is_owner_or_admin(request):
            return Response(
                {"error": {"code": "FORBIDDEN", "message": "Only owner/admin can manage API keys", "details": {}}},
                status=status.HTTP_403_FORBIDDEN,
            )

        tenant_id = _tenant_id(request)
        old = ApiKey.objects.filter(id=api_key_id, tenant_id=tenant_id).first()
        if not old:
            return Response(
                {"error": {"code": "NOT_FOUND", "message": "API key not found", "details": {}}},
                status=status.HTTP_404_NOT_FOUND,
            )

        # revoke old key (idempotent)
        old.revoke()

        # issue new
        raw = generate_raw_key()
        new_row = ApiKey.objects.create(
            tenant_id=tenant_id,
            chatbot_id=old.chatbot_id,
            key_prefix=key_prefix(raw),
            key_hash=hash_key(raw),
            status=ApiKey.Status.ACTIVE,
            rate_limit_per_min=old.rate_limit_per_min,
        )

        return Response(
            {"api_key": {**ApiKeySerializer(new_row).data, "raw_key": raw}},
            status=status.HTTP_200_OK,
        )
