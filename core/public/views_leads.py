from django.db import transaction
from django.utils import timezone

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from core.api_keys.public_auth import ChatbotKeyAuthentication
from core.chatbots.models import Chatbot
from core.conversations.models import Conversation
from core.leads.models import Lead
from core.leads.opensearch import upsert_lead_doc
from core.public.serializers import PublicLeadCaptureSerializer


class PublicLeadCaptureView(APIView):
    """
    POST /v1/public/leads
    Headers:
      X-Chatbot-Key: <raw_key>

    Body:
      {
        "conversation_id": "<uuid optional>",
        "name": "Patel",
        "email": "patel@acme.com",
        "phone": "+91....",
        "meta": {... optional}
      }

    Response 200:
      { "lead": { ... } }
    """
    authentication_classes = [ChatbotKeyAuthentication]
    permission_classes = []

    def post(self, request):
        s = PublicLeadCaptureSerializer(data=request.data)
        s.is_valid(raise_exception=True)

        tenant_id = getattr(request, "public_tenant_id")
        chatbot_id = getattr(request, "public_chatbot_id")

        bot = Chatbot.objects.filter(
            id=chatbot_id, tenant_id=tenant_id, deleted_at__isnull=True
        ).first()
        if not bot or bot.status != Chatbot.Status.ACTIVE:
            return Response(
                {"error": {"code": "NOT_FOUND", "message": "Chatbot not found", "details": {}}},
                status=status.HTTP_404_NOT_FOUND,
            )

        # If your Chatbot model has lead_capture_enabled, enforce it.
        if hasattr(bot, "lead_capture_enabled") and not bool(getattr(bot, "lead_capture_enabled")):
            return Response(
                {"error": {"code": "LEAD_CAPTURE_DISABLED", "message": "Lead capture is disabled", "details": {}}},
                status=status.HTTP_403_FORBIDDEN,
            )

        data = s.validated_data
        conv_id = data.get("conversation_id")

        with transaction.atomic():
            conv = None
            if conv_id:
                conv = Conversation.objects.select_for_update().filter(
                    id=conv_id, tenant_id=tenant_id, chatbot_id=chatbot_id
                ).first()

            # Dedupe strategy:
            # 1) prefer email match, else 2) phone match, else create new
            qs = Lead.objects.select_for_update().filter(
                tenant_id=tenant_id,
                chatbot_id=chatbot_id,
                deleted_at__isnull=True,
            )
            lead = None
            if data["email"]:
                lead = qs.filter(primary_email__iexact=data["email"]).first()
            if not lead and data["phone"]:
                lead = qs.filter(phone=data["phone"]).first()

            if not lead:
                lead = Lead.objects.create(
                    tenant_id=tenant_id,
                    chatbot_id=chatbot_id,
                    conversation=conv,
                    name=data.get("name", "") or "",
                    primary_email=data.get("email", "") or "",
                    phone=data.get("phone", "") or "",
                    status=Lead.Status.NEW,
                    meta_json=data.get("meta") or {},
                )
            else:
                # Merge new info into existing lead (do not wipe)
                changed = False
                if data.get("name") and not lead.name:
                    lead.name = data["name"]
                    changed = True
                if data.get("email") and not lead.primary_email:
                    lead.primary_email = data["email"]
                    changed = True
                if data.get("phone") and not lead.phone:
                    lead.phone = data["phone"]
                    changed = True
                if conv and not lead.conversation_id:
                    lead.conversation = conv
                    changed = True
                if data.get("meta"):
                    lead.meta_json = {**(lead.meta_json or {}), **(data["meta"] or {})}
                    changed = True

                if changed:
                    lead.updated_at = timezone.now()
                    lead.save()

        # Sync to OpenSearch (best-effort; don't fail lead capture if OS is down)
        try:
            upsert_lead_doc(lead=lead)
        except Exception:
            pass

        return Response(
            {
                "lead": {
                    "id": str(lead.id),
                    "tenant_id": str(lead.tenant_id),
                    "chatbot_id": str(lead.chatbot_id),
                    "conversation_id": str(lead.conversation_id) if lead.conversation_id else None,
                    "name": lead.name,
                    "email": lead.primary_email,
                    "phone": lead.phone,
                    "status": lead.status,
                    "email_verified": bool(lead.email_verified),
                    "verified_at": lead.verified_at.isoformat() if lead.verified_at else None,
                    "created_at": lead.created_at.isoformat() if lead.created_at else None,
                    "updated_at": lead.updated_at.isoformat() if lead.updated_at else None,
                }
            },
            status=status.HTTP_200_OK,
        )
