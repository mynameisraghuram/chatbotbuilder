from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone as dt_timezone
from typing import Iterable

TOPIC_KEYWORDS = {
    "pricing": ["price", "pricing", "cost", "charges", "fee", "fees", "plan", "plans", "subscription", "billing"],
    "demo": ["demo", "book a demo", "schedule", "call", "meeting", "appointment"],
    "contact": ["contact", "reach", "phone", "email", "whatsapp", "support number"],
    "integration": ["api", "webhook", "integration", "integrate", "crm", "zapier", "shopify", "wordpress"],
    "security": ["security", "privacy", "gdpr", "soc2", "iso", "encryption", "data retention"],
    "troubleshooting": ["error", "issue", "bug", "not working", "failed", "problem", "crash", "downtime"],
}

INTENT_KEYWORDS = {
    "high_intent": ["buy", "purchase", "subscribe", "signup", "sign up", "pay", "payment", "invoice", "trial", "upgrade"],
    "pricing_intent": TOPIC_KEYWORDS["pricing"],
    "demo_intent": TOPIC_KEYWORDS["demo"],
    "contact_intent": TOPIC_KEYWORDS["contact"],
    "urgent": ["urgent", "asap", "immediately", "today", "now", "emergency"],
}

POSITIVE_WORDS = {"great", "good", "awesome", "perfect", "thanks", "thank you", "helpful", "love"}
NEGATIVE_WORDS = {"bad", "worst", "hate", "angry", "refund", "complaint", "useless", "waste", "broken", "not working"}


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def _count_hits(text: str, keywords: Iterable[str]) -> int:
    t = _norm(text)
    hits = 0
    for kw in keywords:
        if kw in t:
            hits += 1
    return hits


@dataclass(frozen=True)
class SignalSnapshot:
    topics: dict
    intents: dict
    sentiment: str  # "positive" | "negative" | "neutral"
    score: int      # 0..100
    updated_at: str


def build_signals_from_messages(messages: list[str]) -> SignalSnapshot:
    joined = " ".join(_norm(m) for m in messages if m).strip()

    topic_scores = {}
    for topic, kws in TOPIC_KEYWORDS.items():
        topic_scores[topic] = _count_hits(joined, kws)

    intents = {}
    for intent, kws in INTENT_KEYWORDS.items():
        intents[intent] = _count_hits(joined, kws)

    pos = _count_hits(joined, POSITIVE_WORDS)
    neg = _count_hits(joined, NEGATIVE_WORDS)

    if neg > pos and neg > 0:
        sentiment = "negative"
    elif pos > neg and pos > 0:
        sentiment = "positive"
    else:
        sentiment = "neutral"

    # Scoring: simple, deterministic (no AI). Tune later.
    score = 10
    score += min(30, intents.get("high_intent", 0) * 15)
    score += min(25, intents.get("pricing_intent", 0) * 10)
    score += min(20, intents.get("demo_intent", 0) * 12)
    score += min(10, intents.get("contact_intent", 0) * 8)
    score += min(10, intents.get("urgent", 0) * 10)

    if sentiment == "negative":
        score = max(0, score - 10)
    if sentiment == "positive":
        score = min(100, score + 5)

    score = max(0, min(100, score))

    updated_at = datetime.now(dt_timezone.utc).isoformat()

    # Keep only “active” topics/intents to reduce noise
    topics_compact = {k: v for k, v in topic_scores.items() if v > 0}
    intents_compact = {k: v for k, v in intents.items() if v > 0}

    return SignalSnapshot(
        topics=topics_compact,
        intents=intents_compact,
        sentiment=sentiment,
        score=score,
        updated_at=updated_at,
    )
