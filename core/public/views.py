# backend/core/public/views.py

import re
import time
import hashlib
from django.db import transaction
from django.utils import timezone

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from core.api_keys.public_auth import ChatbotKeyAuthentication
from core.common.ratelimit import rate_limit_or_raise, RateLimitExceeded

from core.chatbots.models import Chatbot
from core.conversations.models import Conversation, Message

from core.knowledge.readiness import tenant_knowledge_ready
from core.knowledge.retrieval import search_knowledge_chunks

import random
from datetime import timedelta

from core.leads.models import Lead, OtpVerification
from core.tenants.models import Tenant
from core.common.flags import is_enabled
from core.api_keys.utils import hash_key

from core.public.serializers import (
    PublicLeadCaptureSerializer,
    PublicOtpRequestSerializer,
    PublicOtpConfirmSerializer,
     PublicChatRequestSerializer,
)

def _clean_text(s: str) -> str:
    s = s or ""
    s = s.replace("\x00", " ")
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _dedupe_chunks(chunks):
    """
    De-dupe by normalized content hash (keeps first/highest-scored ordering).
    """
    seen = set()
    out = []
    for c in chunks or []:
        content = _clean_text(getattr(c, "content", "") or "")
        if not content:
            continue
        h = hashlib.sha256(content.encode("utf-8")).hexdigest()
        if h in seen:
            continue
        seen.add(h)
        out.append(c)
    return out


def _compose_reply_from_chunks(
    chunks,
    *,
    max_reply_chars: int = 1400,
    per_chunk_chars: int = 700,
    max_chunks: int = 3,
) -> str:
    """
    Build a readable reply from top chunks with hard limits.
    """
    parts = []
    total = 0

    for c in (chunks or [])[:max_chunks]:
        text = _clean_text(getattr(c, "content", "") or "")
        if not text:
            continue

        text = text[:per_chunk_chars].strip()
        if not text:
            continue

        add = text if not parts else f"\n\n{text}"
        if total + len(add) > max_reply_chars:
            remaining = max_reply_chars - total
            if remaining <= 0:
                break
            add = add[:remaining].rstrip()
            parts.append(add)
            total += len(add)
            break

        parts.append(add)
        total += len(add)

    return "".join(parts).strip()


def _top_citations(chunks, *, max_sources: int = 3):
    """
    Keep only top N unique sources by first occurrence (already score-ordered).
    """
    out = []
    seen_sources = set()

    for c in chunks or []:
        sid = str(getattr(c, "source_id", "") or "")
        if not sid or sid in seen_sources:
            continue
        seen_sources.add(sid)

        out.append(
            {
                "source_id": sid,
                "title": _clean_text(str(getattr(c, "title", "") or ""))[:255],
                "score": round(float(getattr(c, "score", 0.0) or 0.0), 3),
            }
        )
        if len(out) >= max_sources:
            break

    return out


def _rate_limit(request):
    tenant_id = str(getattr(request, "public_tenant_id", ""))
    chatbot_id = str(getattr(request, "public_chatbot_id", ""))
    api_key_id = str(getattr(request, "public_api_key_id", ""))
    limit = int(getattr(request, "public_rate_limit_per_min", 60))

    minute_bucket = int(time.time() // 60)
    rl_key = f"rl:{tenant_id}:{chatbot_id}:{api_key_id}:{minute_bucket}"

    try:
        rate_limit_or_raise(key=rl_key, limit=limit, window_seconds=60)
    except RateLimitExceeded as e:
        return Response(
            {
                "error": {
                    "code": "RATE_LIMITED",
                    "message": "Too many requests",
                    "details": {"retry_after": e.retry_after_seconds},
                }
            },
            status=status.HTTP_429_TOO_MANY_REQUESTS,
            headers={"Retry-After": str(e.retry_after_seconds)},
        )
    return None

def _norm_email(email: str) -> str:
    return (email or "").strip().lower()


def _norm_phone(phone: str) -> str:
    p = (phone or "").strip()
    # keep + and digits only
    cleaned = "".join(ch for ch in p if ch.isdigit() or ch == "+")
    return cleaned


class PublicPingView(APIView):
    authentication_classes = [ChatbotKeyAuthentication]
    permission_classes = []

    def get(self, request):
        rl = _rate_limit(request)
        if rl:
            return rl

        return Response(
            {
                "ok": True,
                "tenant_id": str(getattr(request, "public_tenant_id", "")),
                "chatbot_id": str(getattr(request, "public_chatbot_id", "")),
                "api_key_id": str(getattr(request, "public_api_key_id", "")),
                "rate_limit_per_min": int(getattr(request, "public_rate_limit_per_min", 60)),
            },
            status=200,
        )


class PublicChatView(APIView):
    """
    POST /v1/public/chat
    Headers:
      X-Chatbot-Key: <raw_key>

    Body:
      {
        "conversation_id": "<uuid optional>",
        "message": "hello",
        "external_user_id": "... optional",
        "session_id": "... optional",
        "user_email": "... optional",
        "meta": {... optional }
      }
    """
    authentication_classes = [ChatbotKeyAuthentication]
    permission_classes = []

    def post(self, request):
        rl = _rate_limit(request)
        if rl:
            return rl

        s = PublicChatRequestSerializer(data=request.data)
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

        data = s.validated_data
        user_message = (data.get("message") or "").strip()
        if not user_message:
            return Response(
                {"error": {"code": "VALIDATION_ERROR", "message": "message cannot be empty", "details": {}}},
                status=422,
            )

        # default so msg_meta always has a defined value
        chunks = []
        citations = []

        with transaction.atomic():
            conv = None
            conv_id = data.get("conversation_id")

            if conv_id:
                conv = Conversation.objects.select_for_update().filter(
                    id=conv_id, tenant_id=tenant_id, chatbot_id=chatbot_id
                ).first()

            if not conv:
                conv = Conversation.objects.create(
                    tenant_id=tenant_id,
                    chatbot_id=chatbot_id,
                    external_user_id=data.get("external_user_id", "") or "",
                    session_id=data.get("session_id", "") or "",
                    user_email=data.get("user_email", "") or "",
                    meta_json=data.get("meta", {}) or {},
                )

            Message.objects.create(
                tenant_id=tenant_id,
                conversation=conv,
                role=Message.Role.USER,
                content=user_message,
                meta_json={"ts": timezone.now().isoformat()},
            )

            if not tenant_knowledge_ready(tenant_id=tenant_id):
                assistant_text = (
                    "I’m not ready with your company information yet. "
                    "Please try again in a moment after your content finishes processing."
                )
                citations = []
                chunks = []
            else:
                chunks = search_knowledge_chunks(
                    tenant_id=str(tenant_id),
                    query=user_message,
                    top_k=8,
                    min_score=0.8,
                )
                chunks = _dedupe_chunks(chunks)

                if not chunks:
                    assistant_text = (
                        "I couldn’t find this in your company information yet. "
                        "Try rephrasing, or add more content to your knowledge base."
                    )
                    citations = []
                else:
                    assistant_text = _compose_reply_from_chunks(
                        chunks,
                        max_reply_chars=1400,
                        per_chunk_chars=700,
                        max_chunks=3,
                    )
                    if not assistant_text:
                        assistant_text = "I found related info, but it looks empty. Please try again."

                    citations = _top_citations(chunks, max_sources=3)

            # ---- analytics-ready retrieval metadata (NEW) ----
            top_score = 0.0
            if chunks:
                try:
                    top_score = float(getattr(chunks[0], "score", 0.0) or 0.0)
                except Exception:
                    top_score = 0.0

            source_ids = []
            if citations:
                source_ids = [c.get("source_id") for c in citations if c.get("source_id")]

            msg_meta = {
                "placeholder": False,
                "kb_used": bool(chunks),
                "kb_top_score": round(top_score, 3),
                "kb_source_ids": source_ids,
            }
            if bot.citations_enabled:
                msg_meta["citations"] = citations
            # -----------------------------------------------

            Message.objects.create(
                tenant_id=tenant_id,
                conversation=conv,
                role=Message.Role.ASSISTANT,
                content=assistant_text,
                meta_json=msg_meta,
            )

            conv.updated_at = timezone.now()
            conv.save(update_fields=["updated_at"])

        payload = {"conversation_id": str(conv.id), "reply": assistant_text}
        if bot.citations_enabled:
            payload["citations"] = citations

        return Response(payload, status=status.HTTP_200_OK)



class PublicLeadCaptureView(APIView):
    """
    A7.5
    POST /v1/public/leads
    Header: X-Chatbot-Key

    Body:
      { "name": "...", "email": "...", "phone": "...", "conversation_id": "... optional" }

    Behavior:
      - requires email or phone
      - links existing lead by (tenant,email) then (tenant,phone)
      - creates lead if not found
      - optionally links lead to conversation_id if provided
      - respects chatbot.lead_capture_enabled
      - CRM gated by flags: crm_enabled
    """
    authentication_classes = [ChatbotKeyAuthentication]
    permission_classes = []

    def post(self, request):
        rl = _rate_limit(request)
        if rl:
            return rl

        tenant_id = getattr(request, "public_tenant_id", None)
        chatbot_id = getattr(request, "public_chatbot_id", None)

        bot = Chatbot.objects.filter(id=chatbot_id, tenant_id=tenant_id, deleted_at__isnull=True).first()
        if not bot or bot.status != Chatbot.Status.ACTIVE:
            return Response(
                {"error": {"code": "NOT_FOUND", "message": "Chatbot not found", "details": {}}},
                status=status.HTTP_404_NOT_FOUND,
            )

        if not bot.lead_capture_enabled:
            return Response(
                {"error": {"code": "FEATURE_DISABLED", "message": "Lead capture is disabled", "details": {}}},
                status=status.HTTP_403_FORBIDDEN,
            )

        s = PublicLeadCaptureSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        data = s.validated_data

        name = (data.get("name") or "").strip()
        email = _norm_email(data.get("email") or "")
        phone = _norm_phone(data.get("phone") or "")

        conv_id = data.get("conversation_id")

        with transaction.atomic():
            lead = None

            if email:
                lead = Lead.objects.select_for_update().filter(
                    tenant_id=tenant_id, primary_email=email, deleted_at__isnull=True
                ).order_by("created_at").first()

            if not lead and phone:
                lead = Lead.objects.select_for_update().filter(
                    tenant_id=tenant_id, phone=phone, deleted_at__isnull=True
                ).order_by("created_at").first()

            linked_existing = bool(lead)

            if not lead:
                lead = Lead.objects.create(
                    tenant_id=tenant_id,
                    chatbot_id=chatbot_id,
                    name=name,
                    primary_email=email,
                    phone=phone,
                    status=Lead.Status.NEW,
                    email_verified=False,
                )
            else:
                # merge missing fields (never overwrite existing with empty)
                changed = False
                if name and not lead.name:
                    lead.name = name
                    changed = True
                if email and not lead.primary_email:
                    lead.primary_email = email
                    changed = True
                if phone and not lead.phone:
                    lead.phone = phone
                    changed = True
                if changed:
                    lead.touch()

            # optionally link to conversation (if the conversation belongs to same tenant/bot)
            if conv_id and not lead.conversation_id:
                conv = Conversation.objects.filter(id=conv_id, tenant_id=tenant_id, chatbot_id=chatbot_id).first()
                if conv:
                    lead.conversation = conv
                    lead.touch()

        return Response(
            {
                "lead": {
                    "id": str(lead.id),
                    "name": lead.name,
                    "email": lead.primary_email,
                    "phone": lead.phone,
                    "email_verified": bool(lead.email_verified),
                    "status": lead.status,
                },
                "linked_existing": linked_existing,
            },
            status=status.HTTP_200_OK,
        )


class PublicLeadEmailOtpRequestView(APIView):
    """
    POST /v1/public/leads/{lead_id}/verify-email/request
    Header: X-Chatbot-Key
    Body: { "email": "..." }
    """
    authentication_classes = [ChatbotKeyAuthentication]
    permission_classes = []

    def post(self, request, lead_id):
        rl = _rate_limit(request)
        if rl:
            return rl

        tenant_id = getattr(request, "public_tenant_id", None)
        chatbot_id = getattr(request, "public_chatbot_id", None)

        s = PublicOtpRequestSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        email = _norm_email(s.validated_data["email"])

        lead = Lead.objects.filter(id=lead_id, tenant_id=tenant_id, chatbot_id=chatbot_id, deleted_at__isnull=True).first()
        if not lead:
            return Response({"error": {"code": "NOT_FOUND", "message": "Lead not found", "details": {}}}, status=404)

        # throttle: 3 per 10 minutes per lead+email
        minute_bucket = int(time.time() // 60)
        otp_rl_key = f"otp:request:{tenant_id}:{lead_id}:{email}:{minute_bucket}"
        try:
            rate_limit_or_raise(key=otp_rl_key, limit=3, window_seconds=600)
        except RateLimitExceeded as e:
            return Response(
                {"error": {"code": "RATE_LIMITED", "message": "Too many OTP requests", "details": {"retry_after": e.retry_after_seconds}}},
                status=429,
                headers={"Retry-After": str(e.retry_after_seconds)},
            )

        otp = f"{random.randint(0, 999999):06d}"
        otp_hash = OtpVerification.hash_otp(email, otp)
        expires_at = timezone.now() + timedelta(minutes=5)

        OtpVerification.objects.create(
            tenant_id=tenant_id,
            lead=lead,
            email=email,
            otp_hash=otp_hash,
            expires_at=expires_at,
        )

        # NOTE: Email delivery is intentionally not implemented here.
        # Hook Celery: enqueue an email task with (tenant_id, email, otp)

        return Response({"verification": {"status": "otp_sent", "expires_in_seconds": 300}}, status=202)


class PublicLeadEmailOtpConfirmView(APIView):
    """
    POST /v1/public/leads/{lead_id}/verify-email/confirm
    Header: X-Chatbot-Key
    Body: { "email": "...", "otp": "123456" }
    """
    authentication_classes = [ChatbotKeyAuthentication]
    permission_classes = []

    def post(self, request, lead_id):
        rl = _rate_limit(request)
        if rl:
            return rl

        tenant_id = getattr(request, "public_tenant_id", None)
        chatbot_id = getattr(request, "public_chatbot_id", None)


        s = PublicOtpConfirmSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        email = _norm_email(s.validated_data["email"])
        otp = (s.validated_data["otp"] or "").strip()

        lead = Lead.objects.filter(id=lead_id, tenant_id=tenant_id, chatbot_id=chatbot_id, deleted_at__isnull=True).first()
        if not lead:
            return Response({"error": {"code": "NOT_FOUND", "message": "Lead not found", "details": {}}}, status=404)

        with transaction.atomic():
            ov = (
                OtpVerification.objects.select_for_update()
                .filter(
                    tenant_id=tenant_id,
                    lead=lead,
                    email=email,
                    verified_at__isnull=True,
                )
                .order_by("-created_at")
                .first()
            )

            if not ov:
                return Response({"error": {"code": "VALIDATION_ERROR", "message": "otp_not_found", "details": {}}}, status=422)

            if ov.expires_at < timezone.now():
                return Response({"error": {"code": "VALIDATION_ERROR", "message": "otp_expired", "details": {}}}, status=422)

            if ov.attempt_count >= 5:
                return Response({"error": {"code": "VALIDATION_ERROR", "message": "otp_locked", "details": {}}}, status=422)

            expected = OtpVerification.hash_otp(email, otp)
            if expected != ov.otp_hash:
                ov.attempt_count += 1
                ov.save(update_fields=["attempt_count"])
                return Response(
                    {"error": {"code": "VALIDATION_ERROR", "message": "otp_invalid", "details": {"attempts_left": max(0, 5 - ov.attempt_count)}}},
                    status=422,
                )

            ov.verified_at = timezone.now()
            ov.save(update_fields=["verified_at"])

            lead.primary_email = email
            lead.email_verified = True
            lead.verified_at = ov.verified_at
            lead.touch()

        return Response(
            {"lead": {"id": str(lead.id), "email": lead.primary_email, "email_verified": True, "verified_at": lead.verified_at.isoformat()}},
            status=200,
        )
