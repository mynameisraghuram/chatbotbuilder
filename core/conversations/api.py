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

from rest_framework import status

from core.conversations.lead_serializers import LeadLiteSerializer
from core.leads.models import Lead


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

def _is_owner_admin(member: TenantMembership) -> bool:
    return member.role in (TenantMembership.ROLE_OWNER, TenantMembership.ROLE_ADMIN)

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

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def conversations_search(request):
    """
    GET /v1/conversations/search?chatbot_id=<uuid>&q=...&days=30&limit=20&offset=0

    Postgres search (icontains) over Message.content.
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

    q = (request.query_params.get("q") or "").strip()
    if not q:
        return Response({"error": {"code": "VALIDATION_ERROR", "message": "q is required"}}, status=422)

    # guardrail: prevent huge queries
    if len(q) > 200:
        q = q[:200]

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

    # Only messages for conversations under this tenant + chatbot
    qs = (
        Message.objects.filter(
            tenant_id=tenant_id,
            conversation__tenant_id=tenant_id,
            conversation__chatbot_id=chatbot_id,
            created_at__gte=start,
            created_at__lte=now,
        )
        .exclude(content__isnull=True)
        .exclude(content__exact="")
        .filter(content__icontains=q)
        .select_related("conversation")
        .order_by("-created_at")
    )

    total = qs.count()
    page = qs[offset : offset + limit]

    def _snippet(text: str, needle: str, max_len: int = 220) -> str:
        t = (text or "").strip()
        if not t:
            return ""
        idx = t.lower().find(needle.lower())
        if idx == -1:
            return (t[:max_len] + ("…" if len(t) > max_len else ""))
        start_i = max(0, idx - 60)
        end_i = min(len(t), idx + len(needle) + 140)
        s = t[start_i:end_i]
        if start_i > 0:
            s = "…" + s
        if end_i < len(t):
            s = s + "…"
        if len(s) > max_len:
            s = s[:max_len] + "…"
        return s

    items = []
    for m in page:
        items.append(
            {
                "conversation_id": str(m.conversation_id),
                "message_id": str(m.id),
                "role": m.role,
                "snippet": _snippet(m.content or "", q),
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
        )

    return Response(
        {
            "q": q,
            "chatbot_id": str(chatbot_id),
            "days": days,
            "items": items,
            "page": {"limit": limit, "offset": offset, "total": total},
        }
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def conversation_lead_get(request, conversation_id: str):
    """
    GET /v1/conversations/{conversation_id}/lead
    Requires crm_enabled (server-side gate)
    """
    tenant_id, member, err = _require_tenant_and_member(request)
    if err:
        return err

    if not is_enabled(str(tenant_id), "crm_enabled"):
        return Response(
            {"error": {"code": "FEATURE_DISABLED", "message": "CRM is not enabled for this tenant"}},
            status=403,
        )

    conv = Conversation.objects.filter(id=conversation_id, tenant_id=tenant_id).select_related("lead").first()
    if not conv:
        return Response({"error": {"code": "NOT_FOUND", "message": "Conversation not found"}}, status=404)

    lead = conv.lead
    return Response(
        {
            "conversation_id": str(conv.id),
            "lead": LeadLiteSerializer(lead).data if lead else None,
        },
        status=200,
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def conversation_lead_link(request, conversation_id: str):
    """
    POST /v1/conversations/{conversation_id}/lead/link
    Body: { "lead_id": "<uuid|null>" }

    OWNER/ADMIN only.
    Requires crm_enabled (server-side gate)
    """
    tenant_id, member, err = _require_tenant_and_member(request)
    if err:
        return err

    if not is_enabled(str(tenant_id), "crm_enabled"):
        return Response(
            {"error": {"code": "FEATURE_DISABLED", "message": "CRM is not enabled for this tenant"}},
            status=403,
        )

    if not _is_owner_admin(member):
        return Response(
            {"error": {"code": "FORBIDDEN", "message": "Only owner/admin can link conversations to leads"}},
            status=403,
        )

    conv = Conversation.objects.filter(id=conversation_id, tenant_id=tenant_id).first()
    if not conv:
        return Response({"error": {"code": "NOT_FOUND", "message": "Conversation not found"}}, status=404)

    lead_id = request.data.get("lead_id", None)

    # Unlink
    if lead_id in (None, "", "null"):
        conv.lead_id = None
        conv.save(update_fields=["lead", "updated_at"])
        return Response({"conversation_id": str(conv.id), "lead": None}, status=200)

    # Link (must belong to same tenant)
    lead = Lead.objects.filter(id=lead_id, tenant_id=tenant_id).first()
    if not lead:
        return Response(
            {"error": {"code": "NOT_FOUND", "message": "Lead not found"}},
            status=404,
        )

    conv.lead = lead
    conv.save(update_fields=["lead", "updated_at"])

    return Response(
        {"conversation_id": str(conv.id), "lead": LeadLiteSerializer(lead).data},
        status=200,
    )
