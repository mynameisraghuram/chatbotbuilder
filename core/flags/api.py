from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.iam.models import TenantMembership
from core.common.flags import get_entitlements

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def entitlements(request):
    tenant_id = getattr(request, "tenant_id", None)
    if not tenant_id:
        return Response({"error": {"code": "TENANT_REQUIRED", "message": "X-Tenant-Id header is required"}}, status=400)

    member = TenantMembership.objects.filter(tenant_id=tenant_id, user_id=request.user.id).first()
    if not member:
        return Response({"error": {"code": "FORBIDDEN", "message": "User is not a member of this tenant"}}, status=403)

    flags = get_entitlements(str(tenant_id))
    return Response({"tenant_id": str(tenant_id), "flags": flags})
