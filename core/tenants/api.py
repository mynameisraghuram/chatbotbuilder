from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.tenants.models import Tenant
from core.iam.models import TenantMembership

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def tenant_me(request):
    tenant_id = getattr(request, "tenant_id", None)
    if not tenant_id:
        return Response({"error": {"code": "TENANT_REQUIRED", "message": "X-Tenant-Id header is required"}}, status=400)

    try:
        tenant = Tenant.objects.get(id=tenant_id)
    except Tenant.DoesNotExist:
        return Response({"error": {"code": "TENANT_NOT_FOUND", "message": "Tenant not found"}}, status=404)

    member = TenantMembership.objects.filter(tenant_id=tenant_id, user_id=request.user.id).first()
    if not member:
        return Response({"error": {"code": "FORBIDDEN", "message": "User is not a member of this tenant"}}, status=403)

    return Response({
        "tenant": {"id": str(tenant.id), "name": tenant.name, "status": tenant.status},
        "membership": {"role": member.role},
        "user": {"id": str(request.user.id), "email": request.user.email},
    })
