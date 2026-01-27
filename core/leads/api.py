# repo-root/backend/core/leads/api.py

from django.db.models import Q
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.common.flags import is_enabled
from core.iam.models import TenantMembership
from core.leads.models import Lead
from core.leads.serializers import LeadListSerializer, LeadDetailSerializer, LeadUpdateSerializer


def _require_tenant_and_membership(request):
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


def _require_crm_enabled(tenant_id):
    if not is_enabled(str(tenant_id), "crm_enabled"):
        return Response(
            {"error": {"code": "FEATURE_DISABLED", "message": "CRM is not enabled for this tenant"}},
            status=403,
        )
    return None


def _can_edit(member: TenantMembership) -> bool:
    # viewers cannot edit; owner/admin/editor can
    return member.role in (
        TenantMembership.ROLE_OWNER,
        TenantMembership.ROLE_ADMIN,
        TenantMembership.ROLE_EDITOR,
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def leads_list(request):
    """
    GET /v1/leads
    Headers: Authorization: Bearer <jwt>, X-Tenant-Id: <uuid>

    Query:
      chatbot_id=<uuid optional>
      status=<new|open|qualified|closed optional>
      q=<search optional: name/email/phone>
      limit=<int optional, default 50, max 200>
      offset=<int optional, default 0>
    """
    tenant_id, member, err = _require_tenant_and_membership(request)
    if err:
        return err

    gate = _require_crm_enabled(tenant_id)
    if gate:
        return gate

    chatbot_id = request.query_params.get("chatbot_id") or ""
    status_val = request.query_params.get("status") or ""
    q = (request.query_params.get("q") or "").strip()

    try:
        limit = int(request.query_params.get("limit") or 50)
    except Exception:
        limit = 50
    limit = max(1, min(200, limit))

    try:
        offset = int(request.query_params.get("offset") or 0)
    except Exception:
        offset = 0
    offset = max(0, offset)

    qs = Lead.objects.filter(tenant_id=tenant_id, deleted_at__isnull=True).order_by("-created_at")

    if chatbot_id:
        qs = qs.filter(chatbot_id=chatbot_id)

    if status_val:
        qs = qs.filter(status=status_val)

    if q:
        qs = qs.filter(
            Q(name__icontains=q) |
            Q(primary_email__icontains=q) |
            Q(phone__icontains=q)
        )

    total = qs.count()
    items = qs[offset: offset + limit]

    return Response(
        {
            "items": LeadListSerializer(items, many=True).data,
            "page": {"limit": limit, "offset": offset, "total": total},
        }
    )


@api_view(["GET", "PATCH"])
@permission_classes([IsAuthenticated])
def leads_detail(request, lead_id: str):
    """
    GET /v1/leads/{lead_id}
    PATCH /v1/leads/{lead_id}
    Headers: Authorization: Bearer <jwt>, X-Tenant-Id: <uuid>
    """
    tenant_id, member, err = _require_tenant_and_membership(request)
    if err:
        return err

    gate = _require_crm_enabled(tenant_id)
    if gate:
        return gate

    lead = Lead.objects.filter(id=lead_id, tenant_id=tenant_id, deleted_at__isnull=True).first()
    if not lead:
        return Response(
            {"error": {"code": "NOT_FOUND", "message": "Lead not found"}},
            status=404,
        )

    if request.method == "GET":
        return Response({"lead": LeadDetailSerializer(lead).data})

    # PATCH
    if not _can_edit(member):
        return Response(
            {"error": {"code": "FORBIDDEN", "message": "Insufficient role to update lead"}},
            status=403,
        )

    s = LeadUpdateSerializer(data=request.data)
    s.is_valid(raise_exception=True)
    data = s.validated_data

    changed = False

    if "name" in data:
        lead.name = data["name"]
        changed = True

    if "phone" in data:
        lead.phone = data["phone"]
        changed = True

    if "status" in data:
        lead.status = data["status"]
        changed = True

    if "meta" in data:
        lead.meta_json = {**(lead.meta_json or {}), **(data["meta"] or {})}
        changed = True

    if changed:
        lead.touch()

    return Response({"lead": LeadDetailSerializer(lead).data})
