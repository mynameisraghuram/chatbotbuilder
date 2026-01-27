# repo-root/backend/core/search/leads_api.py

from django.db.models import Q

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.common.flags import is_enabled
from core.iam.models import TenantMembership
from core.leads.models import Lead
from core.leads.serializers import LeadListSerializer
from core.leads.search import search_leads_os


def _require_tenant_and_member(request):
    tenant_id = getattr(request, "tenant_id", None)
    if not tenant_id:
        return None, None, Response({"error": {"code": "TENANT_REQUIRED", "message": "X-Tenant-Id header is required"}}, status=400)

    member = TenantMembership.objects.filter(tenant_id=tenant_id, user_id=request.user.id).first()
    if not member:
        return tenant_id, None, Response({"error": {"code": "FORBIDDEN", "message": "User is not a member of this tenant"}}, status=403)

    return tenant_id, member, None


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def search_leads(request):
    """
    GET /v1/search/leads?q=...
    Headers: Authorization: Bearer <jwt>, X-Tenant-Id: <uuid>
    """
    tenant_id, member, err = _require_tenant_and_member(request)
    if err:
        return err

    if not is_enabled(str(tenant_id), "crm_enabled"):
        return Response({"error": {"code": "FEATURE_DISABLED", "message": "CRM is not enabled for this tenant"}}, status=403)

    q = (request.query_params.get("q") or "").strip()
    if not q:
        return Response({"error": {"code": "VALIDATION_ERROR", "message": "q is required"}}, status=422)

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

    # Prefer OpenSearch, fallback to Postgres
    try:
        total, docs = search_leads_os(tenant_id=str(tenant_id), query=q, limit=limit, offset=offset)
        return Response({"source": "opensearch", "items": docs, "page": {"limit": limit, "offset": offset, "total": total}})
    except Exception:
        qs = Lead.objects.filter(tenant_id=tenant_id, deleted_at__isnull=True).filter(
            Q(name__icontains=q) | Q(primary_email__icontains=q) | Q(phone__icontains=q)
        ).order_by("-updated_at")

        total = qs.count()
        items = qs[offset: offset + limit]
        return Response({"source": "postgres", "items": LeadListSerializer(items, many=True).data, "page": {"limit": limit, "offset": offset, "total": total}})
