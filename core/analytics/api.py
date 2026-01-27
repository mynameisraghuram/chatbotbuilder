from datetime import datetime, timedelta
from django.db.models import Q
from django.utils import timezone

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.common.flags import is_enabled
from core.iam.models import TenantMembership
from core.chatbots.models import Chatbot
from core.conversations.models import Conversation, Message

from django.db.models.functions import TruncDate
from django.db.models import Count

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


def _parse_dt(s: str):
    # Accept: YYYY-MM-DD
    try:
        return datetime.strptime(s, "%Y-%m-%d")
    except Exception:
        return None


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def chatbot_analytics(request, chatbot_id: str):
    """
    GET /v1/analytics/chatbots/{chatbot_id}?from=YYYY-MM-DD&to=YYYY-MM-DD

    Returns:
      - conversations_total
      - messages_total
      - assistant_messages_total
      - kb_hit_rate (assistant messages with meta_json.kb_used == true)
      - unanswered_rate (assistant messages with kb_used == false)
      - top_unanswered_queries (top user messages that led to kb_used == false)
    """
    tenant_id, member, err = _require_tenant_and_member(request)
    if err:
        return err

    if not is_enabled(str(tenant_id), "analytics_enabled"):
        return Response(
            {"error": {"code": "FEATURE_DISABLED", "message": "Analytics is not enabled for this tenant"}},
            status=403,
        )

    bot = Chatbot.objects.filter(id=chatbot_id, tenant_id=tenant_id, deleted_at__isnull=True).first()
    if not bot:
        return Response({"error": {"code": "NOT_FOUND", "message": "Chatbot not found"}}, status=404)

    # Date range (defaults: last 7 days)
    now = timezone.now()
    from_s = (request.query_params.get("from") or "").strip()
    to_s = (request.query_params.get("to") or "").strip()

    dt_from = _parse_dt(from_s)
    dt_to = _parse_dt(to_s)

    if dt_from:
        start = timezone.make_aware(datetime(dt_from.year, dt_from.month, dt_from.day, 0, 0, 0))
    else:
        start = now - timedelta(days=7)

    if dt_to:
        # inclusive end-of-day
        end = timezone.make_aware(datetime(dt_to.year, dt_to.month, dt_to.day, 23, 59, 59))
    else:
        end = now

    # Conversations in range (by updated_at so activity counts)
    conv_qs = Conversation.objects.filter(
        tenant_id=tenant_id,
        chatbot_id=chatbot_id,
        updated_at__gte=start,
        updated_at__lte=end,
    )

    conversations_total = conv_qs.count()

    # Messages in those conversations
    msg_qs = Message.objects.filter(
        tenant_id=tenant_id,
        conversation_id__in=conv_qs.values_list("id", flat=True),
    )

    messages_total = msg_qs.count()

    assistant_qs = msg_qs.filter(role=Message.Role.ASSISTANT)
    assistant_messages_total = assistant_qs.count()

    # kb_used stored in meta_json by your PublicChatView patch
    kb_used_true = assistant_qs.filter(meta_json__kb_used=True).count()
    kb_used_false = assistant_qs.filter(
        Q(meta_json__kb_used=False) | Q(meta_json__kb_used__isnull=True)
    ).count()

    kb_hit_rate = round((kb_used_true / assistant_messages_total), 4) if assistant_messages_total else 0.0
    unanswered_rate = round((kb_used_false / assistant_messages_total), 4) if assistant_messages_total else 0.0

    # Top unanswered user queries:
    # Find assistant messages with kb_used false, take their conversation + nearest previous user msg.
    # Simple heuristic: any user message in those conversations within range; group by content.
    # (Good enough for MVP; we can tighten later with message ordering.)
    unanswered_conv_ids = assistant_qs.filter(
        Q(meta_json__kb_used=False) | Q(meta_json__kb_used__isnull=True)
    ).values_list("conversation_id", flat=True).distinct()

    user_qs = msg_qs.filter(
        role=Message.Role.USER,
        conversation_id__in=unanswered_conv_ids,
    ).exclude(content__isnull=True).exclude(content__exact="")

    # group in python (portable, no DB-specific JSON ops)
    counts = {}
    for m in user_qs.only("content"):
        key = (m.content or "").strip()
        if not key:
            continue
        if len(key) > 2000:
            key = key[:2000]
        counts[key] = counts.get(key, 0) + 1

    top_unanswered = sorted(
        [{"query": k, "count": v} for k, v in counts.items()],
        key=lambda x: x["count"],
        reverse=True,
    )[:10]

    return Response(
        {
            "chatbot_id": str(bot.id),
            "tenant_id": str(tenant_id),
            "range": {"from": start.isoformat(), "to": end.isoformat()},
            "metrics": {
                "conversations_total": conversations_total,
                "messages_total": messages_total,
                "assistant_messages_total": assistant_messages_total,
                "kb_hit_rate": kb_hit_rate,
                "unanswered_rate": unanswered_rate,
            },
            "top_unanswered_queries": top_unanswered,
        }
    )



@api_view(["GET"])
@permission_classes([IsAuthenticated])
def chatbot_trends(request, chatbot_id: str):
    """
    GET /v1/analytics/chatbots/{chatbot_id}/trends?days=30

    Returns daily buckets:
      - conversations_count
      - user_messages_count
      - assistant_messages_count
      - kb_hit_rate (assistant meta_json.kb_used == true / assistant messages)
    """
    tenant_id, member, err = _require_tenant_and_member(request)
    if err:
        return err

    if not is_enabled(str(tenant_id), "analytics_enabled"):
        return Response(
            {"error": {"code": "FEATURE_DISABLED", "message": "Analytics is not enabled for this tenant"}},
            status=403,
        )

    bot = Chatbot.objects.filter(id=chatbot_id, tenant_id=tenant_id, deleted_at__isnull=True).first()
    if not bot:
        return Response({"error": {"code": "NOT_FOUND", "message": "Chatbot not found"}}, status=404)

    try:
        days = int(request.query_params.get("days") or 30)
    except Exception:
        days = 30
    days = max(1, min(90, days))

    now = timezone.now()
    start = now - timedelta(days=days - 1)
    start = start.replace(hour=0, minute=0, second=0, microsecond=0)

    # Conversations bucketed by updated_at date
    conv_buckets = (
        Conversation.objects.filter(
            tenant_id=tenant_id,
            chatbot_id=chatbot_id,
            updated_at__gte=start,
            updated_at__lte=now,
        )
        .annotate(day=TruncDate("updated_at"))
        .values("day")
        .annotate(conversations_count=Count("id"))
        .order_by("day")
    )
    conv_map = {str(x["day"]): int(x["conversations_count"]) for x in conv_buckets}

    # Messages bucketed by created_at date (more accurate for volume)
    msg_base = Message.objects.filter(
        tenant_id=tenant_id,
        conversation__tenant_id=tenant_id,
        conversation__chatbot_id=chatbot_id,
        created_at__gte=start,
        created_at__lte=now,
    ).select_related("conversation")

    user_buckets = (
        msg_base.filter(role=Message.Role.USER)
        .annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(cnt=Count("id"))
        .order_by("day")
    )
    user_map = {str(x["day"]): int(x["cnt"]) for x in user_buckets}

    assistant_buckets = (
        msg_base.filter(role=Message.Role.ASSISTANT)
        .annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(cnt=Count("id"))
        .order_by("day")
    )
    assistant_map = {str(x["day"]): int(x["cnt"]) for x in assistant_buckets}

    assistant_kb_true_buckets = (
        msg_base.filter(role=Message.Role.ASSISTANT, meta_json__kb_used=True)
        .annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(cnt=Count("id"))
        .order_by("day")
    )
    kb_true_map = {str(x["day"]): int(x["cnt"]) for x in assistant_kb_true_buckets}

    # Build dense series for last N days (including zeros)
    series = []
    for i in range(days):
        d = (start + timedelta(days=i)).date()
        key = str(d)

        conversations_count = conv_map.get(key, 0)
        user_messages_count = user_map.get(key, 0)
        assistant_messages_count = assistant_map.get(key, 0)
        kb_true = kb_true_map.get(key, 0)

        kb_hit_rate = round((kb_true / assistant_messages_count), 4) if assistant_messages_count else 0.0

        series.append(
            {
                "day": key,
                "conversations_count": conversations_count,
                "user_messages_count": user_messages_count,
                "assistant_messages_count": assistant_messages_count,
                "kb_hit_rate": kb_hit_rate,
            }
        )

    return Response(
        {
            "chatbot_id": str(bot.id),
            "tenant_id": str(tenant_id),
            "days": days,
            "from": start.date().isoformat(),
            "to": now.date().isoformat(),
            "series": series,
        }
    )

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def chatbot_top_queries(request, chatbot_id: str):
    """
    GET /v1/analytics/chatbots/{chatbot_id}/top-queries?days=30&limit=20
    """
    tenant_id, member, err = _require_tenant_and_member(request)
    if err:
        return err

    if not is_enabled(str(tenant_id), "analytics_enabled"):
        return Response(
            {"error": {"code": "FEATURE_DISABLED", "message": "Analytics is not enabled for this tenant"}},
            status=403,
        )

    bot = Chatbot.objects.filter(id=chatbot_id, tenant_id=tenant_id, deleted_at__isnull=True).first()
    if not bot:
        return Response({"error": {"code": "NOT_FOUND", "message": "Chatbot not found"}}, status=404)

    try:
        days = int(request.query_params.get("days") or 30)
    except Exception:
        days = 30
    days = max(1, min(90, days))

    try:
        limit = int(request.query_params.get("limit") or 20)
    except Exception:
        limit = 20
    limit = max(1, min(100, limit))

    now = timezone.now()
    start = now - timedelta(days=days - 1)
    start = start.replace(hour=0, minute=0, second=0, microsecond=0)

    # Conversations in range
    conv_ids = list(
        Conversation.objects.filter(
            tenant_id=tenant_id,
            chatbot_id=chatbot_id,
            updated_at__gte=start,
            updated_at__lte=now,
        ).values_list("id", flat=True)
    )

    if not conv_ids:
        return Response(
            {
                "chatbot_id": str(bot.id),
                "tenant_id": str(tenant_id),
                "days": days,
                "top_queries": [],
                "top_unanswered_queries": [],
            }
        )

    # Messages within those conversations (restrict by created_at range)
    msg_qs = Message.objects.filter(
        tenant_id=tenant_id,
        conversation_id__in=conv_ids,
        created_at__gte=start,
        created_at__lte=now,
    )

    # Count all user queries
    user_msgs = msg_qs.filter(role=Message.Role.USER).exclude(content__isnull=True).exclude(content__exact="")
    counts = {}
    for m in user_msgs.only("content"):
        q = (m.content or "").strip()
        if not q:
            continue
        if len(q) > 2000:
            q = q[:2000]
        counts[q] = counts.get(q, 0) + 1

    top_queries = sorted(
        [{"query": k, "count": v} for k, v in counts.items()],
        key=lambda x: x["count"],
        reverse=True,
    )[:limit]

    # Unanswered conversations (assistant kb_used false OR missing)
    unanswered_conv_ids = set(
        msg_qs.filter(role=Message.Role.ASSISTANT)
        .filter(Q(meta_json__kb_used=False) | Q(meta_json__kb_used__isnull=True))
        .values_list("conversation_id", flat=True)
        .distinct()
    )

    if unanswered_conv_ids:
        unanswered_user_msgs = msg_qs.filter(
            role=Message.Role.USER,
            conversation_id__in=list(unanswered_conv_ids),
        ).exclude(content__isnull=True).exclude(content__exact="")

        ucounts = {}
        for m in unanswered_user_msgs.only("content"):
            q = (m.content or "").strip()
            if not q:
                continue
            if len(q) > 2000:
                q = q[:2000]
            ucounts[q] = ucounts.get(q, 0) + 1

        top_unanswered = sorted(
            [{"query": k, "count": v} for k, v in ucounts.items()],
            key=lambda x: x["count"],
            reverse=True,
        )[:limit]
    else:
        top_unanswered = []

    return Response(
        {
            "chatbot_id": str(bot.id),
            "tenant_id": str(tenant_id),
            "days": days,
            "top_queries": top_queries,
            "top_unanswered_queries": top_unanswered,
        }
    )

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def chatbot_gaps(request, chatbot_id: str):
    """
    GET /v1/analytics/chatbots/{chatbot_id}/gaps?days=30&limit=20

    "Gap" = user questions in conversations where the assistant did NOT use KB
            (meta_json.kb_used == false OR missing/null)
    """
    tenant_id, member, err = _require_tenant_and_member(request)
    if err:
        return err

    if not is_enabled(str(tenant_id), "analytics_enabled"):
        return Response(
            {"error": {"code": "FEATURE_DISABLED", "message": "Analytics is not enabled for this tenant"}},
            status=403,
        )

    bot = Chatbot.objects.filter(id=chatbot_id, tenant_id=tenant_id, deleted_at__isnull=True).first()
    if not bot:
        return Response({"error": {"code": "NOT_FOUND", "message": "Chatbot not found"}}, status=404)

    try:
        days = int(request.query_params.get("days") or 30)
    except Exception:
        days = 30
    days = max(1, min(90, days))

    try:
        limit = int(request.query_params.get("limit") or 20)
    except Exception:
        limit = 20
    limit = max(1, min(100, limit))

    now = timezone.now()
    start = now - timedelta(days=days - 1)
    start = start.replace(hour=0, minute=0, second=0, microsecond=0)

    # Conversations in range (activity-based)
    conv_ids = list(
        Conversation.objects.filter(
            tenant_id=tenant_id,
            chatbot_id=chatbot_id,
            updated_at__gte=start,
            updated_at__lte=now,
        ).values_list("id", flat=True)
    )

    if not conv_ids:
        return Response(
            {
                "chatbot_id": str(bot.id),
                "tenant_id": str(tenant_id),
                "days": days,
                "unanswered_queries": [],
            }
        )

    msg_qs = Message.objects.filter(
        tenant_id=tenant_id,
        conversation_id__in=conv_ids,
        created_at__gte=start,
        created_at__lte=now,
    )

    unanswered_conv_ids = set(
        msg_qs.filter(role=Message.Role.ASSISTANT)
        .filter(Q(meta_json__kb_used=False) | Q(meta_json__kb_used__isnull=True))
        .values_list("conversation_id", flat=True)
        .distinct()
    )

    if not unanswered_conv_ids:
        return Response(
            {
                "chatbot_id": str(bot.id),
                "tenant_id": str(tenant_id),
                "days": days,
                "unanswered_queries": [],
            }
        )

    user_msgs = (
        msg_qs.filter(role=Message.Role.USER, conversation_id__in=list(unanswered_conv_ids))
        .exclude(content__isnull=True)
        .exclude(content__exact="")
    )

    # Aggregate in python to stay DB-portable
    counts = {}
    examples = {}  # query -> set(conversation_id)

    for m in user_msgs.only("content", "conversation_id"):
        q = (m.content or "").strip()
        if not q:
            continue
        if len(q) > 2000:
            q = q[:2000]

        counts[q] = counts.get(q, 0) + 1
        if q not in examples:
            examples[q] = set()
        if len(examples[q]) < 3:
            examples[q].add(str(m.conversation_id))

    items = sorted(
        [{"query": k, "count": v, "examples": sorted(list(examples.get(k, [])))} for k, v in counts.items()],
        key=lambda x: x["count"],
        reverse=True,
    )[:limit]

    return Response(
        {
            "chatbot_id": str(bot.id),
            "tenant_id": str(tenant_id),
            "days": days,
            "unanswered_queries": items,
        }
    )
