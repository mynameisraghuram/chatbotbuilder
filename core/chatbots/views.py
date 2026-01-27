from rest_framework import status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.chatbots.models import Chatbot
from core.chatbots.serializers import ChatbotSerializer, ChatbotCreateSerializer
from core.common.flags import is_enabled
from core.iam.permissions import IsTenantMember, HasRole


class ChatbotViewSet(viewsets.ModelViewSet):
    serializer_class = ChatbotSerializer
    permission_classes = [IsAuthenticated, IsTenantMember]

    def get_queryset(self):
        tenant_id = getattr(self.request, "tenant_id", None)
        return Chatbot.objects.filter(tenant_id=tenant_id, deleted_at__isnull=True).order_by("-created_at")

    def create(self, request, *args, **kwargs):
        tenant_id = getattr(request, "tenant_id", None)

        # RBAC: viewer cannot create
        if getattr(request, "tenant_role", None) == "viewer":
            return Response(
                {"error": {"code": "FORBIDDEN", "message": "Insufficient role"}},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Plan gating via feature flag: multibot
        if not is_enabled(str(tenant_id), "multibot"):
            existing_count = Chatbot.objects.filter(tenant_id=tenant_id, deleted_at__isnull=True).count()
            if existing_count >= 1:
                return Response(
                    {
                        "error": {
                            "code": "PLAN_RESTRICTED",
                            "message": "Multiple chatbots are not available on your current plan.",
                            "details": {"feature_key": "multibot"},
                        }
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )

        s = ChatbotCreateSerializer(data=request.data)
        s.is_valid(raise_exception=True)

        data = s.validated_data
        bot = Chatbot.objects.create(
            tenant_id=tenant_id,
            name=data["name"],
            tone=data.get("tone", Chatbot.Tone.FRIENDLY),
            branding_json=data.get("branding_json", {}) or {},
            lead_capture_enabled=bool(data.get("lead_capture_enabled", False)),
            citations_enabled=bool(data.get("citations_enabled", False)),
        )
        return Response(ChatbotSerializer(bot).data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs):
        # RBAC: viewer cannot update
        if getattr(request, "tenant_role", None) == "viewer":
            return Response(
                {"error": {"code": "FORBIDDEN", "message": "Insufficient role"}},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        # RBAC: only owner/admin can delete
        if getattr(request, "tenant_role", None) not in ("owner", "admin"):
            return Response(
                {"error": {"code": "FORBIDDEN", "message": "Only owner/admin can delete chatbots"}},
                status=status.HTTP_403_FORBIDDEN,
            )
        bot = self.get_object()
        bot.soft_delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
