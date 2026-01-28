from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.audit.models import AuditLog


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def audit_logs(request):
    tenant_id = getattr(request, "tenant_id", None)

    qs = AuditLog.objects.filter(tenant_id=tenant_id).order_by("-created_at")[:200]

    return Response({
        "items": [
            {
                "action": a.action,
                "entity_type": a.entity_type,
                "entity_id": a.entity_id,
                "actor_user_id": a.actor_user_id,
                "data": a.data_json,
                "created_at": a.created_at,
            }
            for a in qs
        ]
    })
