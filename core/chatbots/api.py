from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.utils import timezone

from core.iam.models import TenantMembership
from core.chatbots.models import Chatbot
from core.chatbots.serializers import ChatbotUpdateSerializer


def _require_tenant_and_membership(request):
    tenant_id = getattr(request, "tenant_id", None)
    if not tenant_id:
        return None, None, Response({"error": {"code": "TENANT_REQUIRED", "message": "X-Tenant-Id header is required"}}, status=400)

    member = TenantMembership.objects.filter(tenant_id=tenant_id, user_id=request.user.id).first()
    if not member:
        return tenant_id, None, Response({"error": {"code": "FORBIDDEN", "message": "User is not a member of this tenant"}}, status=403)
    return tenant_id, member, None


def _can_edit_chatbot(member: TenantMembership) -> bool:
    return member.role in (
        TenantMembership.ROLE_OWNER,
        TenantMembership.ROLE_ADMIN,
        TenantMembership.ROLE_EDITOR,
    )


@api_view(["PATCH"])
@permission_classes([IsAuthenticated])
def chatbot_update(request, chatbot_id: str):
    """
    PATCH /v1/chatbots/{chatbot_id}
    Headers: Authorization: Bearer <jwt>, X-Tenant-Id: <uuid>
    Body: { "lead_capture_enabled": true/false, ... }
    """
    tenant_id, member, err = _require_tenant_and_membership(request)
    if err:
        return err

    if not _can_edit_chatbot(member):
        return Response({"error": {"code": "FORBIDDEN", "message": "Insufficient role"}}, status=403)

    bot = Chatbot.objects.filter(id=chatbot_id, tenant_id=tenant_id, deleted_at__isnull=True).first()
    if not bot:
        return Response({"error": {"code": "NOT_FOUND", "message": "Chatbot not found"}}, status=404)

    s = ChatbotUpdateSerializer(data=request.data)
    s.is_valid(raise_exception=True)
    data = s.validated_data

    changed = False

    if "lead_capture_enabled" in data:
        # ✅ Only update if field exists on model
        if hasattr(bot, "lead_capture_enabled"):
            bot.lead_capture_enabled = bool(data["lead_capture_enabled"])
            changed = True

    if "citations_enabled" in data and hasattr(bot, "citations_enabled"):
        bot.citations_enabled = bool(data["citations_enabled"])
        changed = True

    if "name" in data and hasattr(bot, "name"):
        bot.name = data["name"]
        changed = True

    if "status" in data and hasattr(bot, "status"):
        bot.status = data["status"]
        changed = True

    if changed:
        bot.updated_at = timezone.now()
        bot.save()

    return Response(
        {
            "chatbot": {
                "id": str(bot.id),
                "tenant_id": str(bot.tenant_id),
                "name": getattr(bot, "name", ""),
                "status": getattr(bot, "status", ""),
                "citations_enabled": bool(getattr(bot, "citations_enabled", False)),
                "lead_capture_enabled": bool(getattr(bot, "lead_capture_enabled", False)),
                "updated_at": bot.updated_at.isoformat() if getattr(bot, "updated_at", None) else None,
            }
        }
    )
