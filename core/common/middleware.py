import uuid
from django.conf import settings
from django.http import JsonResponse

PUBLIC_PATH_PREFIXES = (
    "/admin/",
    "/api/schema/",
    "/api/docs/",
    "/v1/auth/login",
    "/v1/auth/refresh",
)

class TenantScopeMiddleware:
    """
    Sprint 0:
    - Require X-Tenant-Id for /v1/* except auth/docs/admin.
    - Parse UUID and attach request.tenant_id.
    - Membership checks are enforced in endpoints/permissions (server-side).
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path or "/"

        if path.startswith(PUBLIC_PATH_PREFIXES):
            return self.get_response(request)

        if not path.startswith("/v1/"):
            return self.get_response(request)

        header_name = getattr(settings, "TENANT_HEADER", "X-Tenant-Id")
        raw = request.headers.get(header_name)

        if not raw:
            return JsonResponse({"error": {"code": "TENANT_REQUIRED", "message": f"{header_name} header is required"}}, status=400)

        try:
            request.tenant_id = uuid.UUID(str(raw))
        except Exception:
            return JsonResponse({"error": {"code": "TENANT_INVALID", "message": f"{header_name} must be a valid UUID"}}, status=400)

        return self.get_response(request)
