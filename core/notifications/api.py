from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.iam.models import TenantMembership
from core.notifications.models import NotificationPreference
from core.notifications.serializers import (
    NotificationPreferenceOutSerializer,
    NotificationPreferenceUpdateSerializer,
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


def _as_out(pref: NotificationPreference):
    return {
        "tenant_id": pref.tenant_id,
        "user_id": pref.user_id,
        "email_enabled": pref.email_enabled,
        "webhook_enabled": pref.webhook_enabled,
        "digest_mode": pref.digest_mode,
        "digest_hour": pref.digest_hour,
    }


@api_view(["GET", "PATCH"])
@permission_classes([IsAuthenticated])
def my_notification_preferences(request):
    """
    GET   /v1/notifications/preferences/me
    PATCH /v1/notifications/preferences/me
    Headers: Authorization, X-Tenant-Id
    """
    tenant_id, member, err = _require_tenant_and_membership(request)
    if err:
        return err

    pref, _ = NotificationPreference.objects.get_or_create(
        tenant_id=tenant_id,
        user_id=request.user.id,
        defaults={
            "email_enabled": True,
            "webhook_enabled": True,
            "digest_mode": NotificationPreference.DigestMode.OFF,
            "digest_hour": None,
        },
    )

    if request.method == "GET":
        return Response({"preferences": NotificationPreferenceOutSerializer(_as_out(pref)).data})

    s = NotificationPreferenceUpdateSerializer(data=request.data)
    s.is_valid(raise_exception=True)
    data = s.validated_data

    changed = False
    for k in ("email_enabled", "webhook_enabled", "digest_mode", "digest_hour"):
        if k in data:
            setattr(pref, k, data[k])
            changed = True

    if changed:
        pref.touch()
        pref.save(update_fields=["email_enabled", "webhook_enabled", "digest_mode", "digest_hour", "updated_at"])

    return Response({"preferences": NotificationPreferenceOutSerializer(_as_out(pref)).data})
