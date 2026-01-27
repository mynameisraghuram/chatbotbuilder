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
from core.public.serializers import PublicChatRequestSerializer

from core.chatbots.models import Chatbot
from core.conversations.models import Conversation, Message

from core.knowledge.readiness import tenant_knowledge_ready
from core.knowledge.retrieval import search_knowledge_chunks


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
