from django.db import models
from django.db.models import Count, Q
from django.utils import timezone

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.common.flags import is_enabled
from core.iam.models import TenantMembership
from core.leads.models import Lead


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def sla_metrics(request):
    tenant_id = getattr(request, "tenant_id", None)
    if not tenant_id:
        return Response({"error": {"code": "TENANT_REQUIRED"}}, status=400)

    if not is_enabled(str(tenant_id), "lead_sla_enabled"):
        return Response(
            {"error": {"code": "FEATURE_DISABLED", "message": "SLA not enabled"}},
            status=403,
        )

    member = TenantMembership.objects.filter(
        tenant_id=tenant_id,
        user_id=request.user.id,
    ).first()
    if not member:
        return Response({"error": {"code": "FORBIDDEN"}}, status=403)

    now = timezone.now()

    qs = Lead.objects.filter(
        tenant_id=tenant_id,
        deleted_at__isnull=True,
        next_action_at__isnull=False,
    )

    breached_q = Q(next_action_at__lt=now) & (
        Q(last_contacted_at__isnull=True)
        | Q(last_contacted_at__lt=models.F("next_action_at"))
    )

    total_open = qs.count()
    breached = qs.filter(breached_q).count()

    by_status = (
        qs.filter(breached_q)
        .values("status")
        .annotate(breached=Count("id"))
        .order_by()
    )

    by_assignee = (
        qs.filter(breached_q, assigned_to_user_id__isnull=False)
        .values("assigned_to_user_id")
        .annotate(breached=Count("id"))
        .order_by()
    )

    return Response({
        "summary": {
            "total_open": total_open,
            "breached": breached,
            "breach_rate": round(breached / total_open, 4) if total_open else 0,
        },
        "by_status": list(by_status),
        "by_assignee": [
            {"user_id": r["assigned_to_user_id"], "breached": r["breached"]}
            for r in by_assignee
        ],
    })
