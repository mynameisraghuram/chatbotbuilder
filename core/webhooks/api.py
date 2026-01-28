import secrets

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.common.flags import is_enabled
from core.iam.models import TenantMembership
from core.webhooks.models import WebhookEndpoint
from core.webhooks.serializers import (
    WebhookEndpointOutSerializer,
    WebhookEndpointCreateSerializer,
    WebhookEndpointUpdateSerializer,
)


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


def _require_webhooks_enabled(tenant_id):
    if not is_enabled(str(tenant_id), "webhooks_enabled"):
        return Response(
            {"error": {"code": "FEATURE_DISABLED", "message": "Webhooks are not enabled for this tenant"}},
            status=403,
        )
    return None


def _can_write(member: TenantMembership) -> bool:
    return member.role in (
        TenantMembership.ROLE_OWNER,
        TenantMembership.ROLE_ADMIN,
    )


def _as_out(endpoint: WebhookEndpoint):
    return {
        "id": endpoint.id,
        "tenant_id": endpoint.tenant_id,
        "url": endpoint.url,
        "is_active": endpoint.is_active,
        "events": endpoint.events_json or [],
        "created_at": endpoint.created_at,
        "updated_at": endpoint.updated_at,
    }


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def webhook_endpoints(request):
    """
    GET  /v1/webhooks/endpoints
    POST /v1/webhooks/endpoints
    Headers: Authorization, X-Tenant-Id
    """
    tenant_id, member, err = _require_tenant_and_membership(request)
    if err:
        return err

    gate = _require_webhooks_enabled(tenant_id)
    if gate:
        return gate

    if request.method == "GET":
        qs = WebhookEndpoint.objects.filter(tenant_id=tenant_id).order_by("-created_at")
        items = [_as_out(x) for x in qs]
        return Response({"items": WebhookEndpointOutSerializer(items, many=True).data})

    # POST create
    if not _can_write(member):
        return Response(
            {"error": {"code": "FORBIDDEN", "message": "Only owner/admin can manage webhooks"}},
            status=403,
        )

    s = WebhookEndpointCreateSerializer(data=request.data)
    s.is_valid(raise_exception=True)
    data = s.validated_data

    secret_value = secrets.token_urlsafe(32)

    ep = WebhookEndpoint.objects.create(
        tenant_id=tenant_id,
        url=data["url"],
        is_active=data.get("is_active", True),
        events_json=data.get("events", []) or [],
        secret=secret_value,
    )

    # Return secret only on create
    out = _as_out(ep)
    out["secret"] = secret_value

    return Response({"endpoint": out}, status=201)


@api_view(["GET", "PATCH"])
@permission_classes([IsAuthenticated])
def webhook_endpoint_detail(request, endpoint_id: str):
    """
    GET   /v1/webhooks/endpoints/{endpoint_id}
    PATCH /v1/webhooks/endpoints/{endpoint_id}
    """
    tenant_id, member, err = _require_tenant_and_membership(request)
    if err:
        return err

    gate = _require_webhooks_enabled(tenant_id)
    if gate:
        return gate

    ep = WebhookEndpoint.objects.filter(id=endpoint_id, tenant_id=tenant_id).first()
    if not ep:
        return Response({"error": {"code": "NOT_FOUND", "message": "Webhook endpoint not found"}}, status=404)

    if request.method == "GET":
        return Response({"endpoint": WebhookEndpointOutSerializer(_as_out(ep)).data})

    # PATCH
    if not _can_write(member):
        return Response(
            {"error": {"code": "FORBIDDEN", "message": "Only owner/admin can manage webhooks"}},
            status=403,
        )

    s = WebhookEndpointUpdateSerializer(data=request.data)
    s.is_valid(raise_exception=True)
    data = s.validated_data

    changed = False
    if "url" in data:
        ep.url = data["url"]
        changed = True
    if "is_active" in data:
        ep.is_active = data["is_active"]
        changed = True
    if "events" in data:
        ep.events_json = data["events"] or []
        changed = True

    if changed:
        ep.touch()

    return Response({"endpoint": WebhookEndpointOutSerializer(_as_out(ep)).data})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def webhook_endpoint_rotate_secret(request, endpoint_id: str):
    """
    POST /v1/webhooks/endpoints/{endpoint_id}/rotate-secret
    Returns new secret once.
    """
    tenant_id, member, err = _require_tenant_and_membership(request)
    if err:
        return err

    gate = _require_webhooks_enabled(tenant_id)
    if gate:
        return gate

    if not _can_write(member):
        return Response(
            {"error": {"code": "FORBIDDEN", "message": "Only owner/admin can rotate webhook secrets"}},
            status=403,
        )

    ep = WebhookEndpoint.objects.filter(id=endpoint_id, tenant_id=tenant_id).first()
    if not ep:
        return Response({"error": {"code": "NOT_FOUND", "message": "Webhook endpoint not found"}}, status=404)

    new_secret = secrets.token_urlsafe(32)
    ep.secret = new_secret
    ep.touch()
    ep.save(update_fields=["secret", "updated_at"])

    return Response({"endpoint_id": str(ep.id), "secret": new_secret}, status=200)
