from datetime import timedelta
from django.utils import timezone

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.common.flags import is_enabled
from core.iam.models import TenantMembership
from core.conversations.models import Conversation
from core.conversations.serializers import ConversationListSerializer, ConversationDetailSerializer


def _require_tenant_and_member(request):
    tenant_id = getattr(request, "tenant_id", None)
    if not tenant_id:
        return None, None, Response(
            {"error": {"code": "TENANT_REQUIRED", "message": "X-Tenant-Id header is required"}},
            status=400,
        )

    member = TenantMembership.objects.filter(tenant_id=tenant_id, user_id=request.user.id).first()
    if not member:
        return tenant_id, None, Response(
            {"error": {"code": "FORBIDDEN", "message": "User is not a member of this tenant"}},
            status=403,
        )

    return tenant_id, member, None


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def conversations_list(request):
    """
    GET /v1/conversations?chatbot_id=<uuid>&days=30&limit=20&offset=0
    """
    tenant_id, member, err = _require_tenant_and_member(request)
    if err:
        return err

    if not is_enabled(str(tenant_id), "analytics_enabled"):
        return Response(
            {"error": {"code": "FEATURE_DISABLED", "message": "Analytics is not enabled for this tenant"}},
            status=403,
        )

    chatbot_id = (request.query_params.get("chatbot_id") or "").strip()
    if not chatbot_id:
        return Response({"error": {"code": "VALIDATION_ERROR", "message": "chatbot_id is required"}}, status=422)

    try:
        days = int(request.query_params.get("days") or 30)
    except Exception:
        days = 30
    days = max(1, min(90, days))

    try:
        limit = int(request.query_params.get("limit") or 20)
    except Exception:
        limit = 20
    limit = max(1, min(50, limit))

    try:
        offset = int(request.query_params.get("offset") or 0)
    except Exception:
        offset = 0
    offset = max(0, offset)

    now = timezone.now()
    start = now - timedelta(days=days - 1)
    start = start.replace(hour=0, minute=0, second=0, microsecond=0)

    qs = Conversation.objects.filter(
        tenant_id=tenant_id,
        chatbot_id=chatbot_id,
        updated_at__gte=start,
        updated_at__lte=now,
    ).order_by("-updated_at")

    total = qs.count()
    page = qs[offset : offset + limit]

    return Response(
        {
            "items": ConversationListSerializer(page, many=True).data,
            "page": {"limit": limit, "offset": offset, "total": total},
        }
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def conversation_detail(request, conversation_id: str):
    """
    GET /v1/conversations/{conversation_id}
    """
    tenant_id, member, err = _require_tenant_and_member(request)
    if err:
        return err

    if not is_enabled(str(tenant_id), "analytics_enabled"):
        return Response(
            {"error": {"code": "FEATURE_DISABLED", "message": "Analytics is not enabled for this tenant"}},
            status=403,
        )

    conv = Conversation.objects.filter(id=conversation_id, tenant_id=tenant_id).first()
    if not conv:
        return Response({"error": {"code": "NOT_FOUND", "message": "Conversation not found"}}, status=404)

    return Response({"conversation": ConversationDetailSerializer(conv).data})
