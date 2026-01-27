from datetime import timedelta
from django.utils import timezone
from django.db.models import Exists, OuterRef, Q

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.common.flags import is_enabled
from core.iam.models import TenantMembership
from core.conversations.models import Conversation, Message
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


def _can_view_pii(member: TenantMembership) -> bool:
    return member.role in (
        TenantMembership.ROLE_OWNER,
        TenantMembership.ROLE_ADMIN,
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def conversations_list(request):
    """
    GET /v1/conversations?chatbot_id=<uuid>&days=30&limit=20&offset=0&kb_used=true|false|any&include_pii=true

    Notes:
      - include_pii only for OWNER/ADMIN; otherwise ignored.
      - kb_used filter checks assistant messages in the same conversation.
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

    kb_used = (request.query_params.get("kb_used") or "any").strip().lower()
    if kb_used not in ("true", "false", "any"):
        return Response(
            {"error": {"code": "VALIDATION_ERROR", "message": "kb_used must be one of: true,false,any"}},
            status=422,
        )

    include_pii_raw = (request.query_params.get("include_pii") or "").strip().lower()
    include_pii = (include_pii_raw in ("1", "true", "yes")) and _can_view_pii(member)

    now = timezone.now()
    start = now - timedelta(days=days - 1)
    start = start.replace(hour=0, minute=0, second=0, microsecond=0)

    qs = Conversation.objects.filter(
        tenant_id=tenant_id,
        chatbot_id=chatbot_id,
        updated_at__gte=start,
        updated_at__lte=now,
    )

    # kb_used filter via EXISTS subquery on assistant messages
    # (We do not restrict assistant msg timestamps here; it's "conversation had unanswered/answered in this window")
    assistant_base = Message.objects.filter(
        tenant_id=tenant_id,
        conversation_id=OuterRef("id"),
        role=Message.Role.ASSISTANT,
    )

    if kb_used == "true":
        qs = qs.annotate(_kb_true=Exists(assistant_base.filter(meta_json__kb_used=True))).filter(_kb_true=True)
    elif kb_used == "false":
        qs = qs.annotate(
            _kb_false=Exists(
                assistant_base.filter(Q(meta_json__kb_used=False) | Q(meta_json__kb_used__isnull=True))
            )
        ).filter(_kb_false=True)

    qs = qs.order_by("-updated_at")

    total = qs.count()
    page = qs[offset: offset + limit]

    return Response(
        {
            "items": ConversationListSerializer(page, many=True, context={"include_pii": include_pii}).data,
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
