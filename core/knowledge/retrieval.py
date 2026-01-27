from dataclasses import dataclass
from typing import List, Optional

from django.conf import settings
from opensearchpy import OpenSearch


@dataclass
class RetrievedChunk:
    source_id: str
    title: str
    content: str
    score: float


def _client() -> OpenSearch:
    host = getattr(settings, "OPENSEARCH_HOST", "http://localhost:9200")
    timeout = getattr(settings, "OPENSEARCH_TIMEOUT", 15)
    return OpenSearch(hosts=[host], timeout=timeout)


def search_knowledge_chunks(
    *,
    tenant_id: str,
    query: str,
    top_k: int = 5,
    min_score: float = 0.8,
) -> List[RetrievedChunk]:
    index_name = getattr(settings, "OPENSEARCH_KB_INDEX", "kb_chunks_v1")

    FIELD_TENANT = "tenant_id"
    FIELD_SOURCE = "source_id"
    FIELD_TITLE = "title"
    FIELD_CONTENT = "content"

    q = (query or "").strip()
    if not q:
        return []

    # Ignore very short queries (reduces irrelevant matches)
    if len(q) < 3:
        return []

    body = {
        "size": top_k,
        "_source": [FIELD_SOURCE, FIELD_TITLE, FIELD_CONTENT],
        "query": {
            "bool": {
                "filter": [{"term": {FIELD_TENANT: tenant_id}}],
                "must": [
                    {
                        "multi_match": {
                            "query": q,
                            "fields": [FIELD_CONTENT, f"{FIELD_TITLE}^2"],
                            "type": "best_fields",
                            "operator": "and",
                        }
                    }
                ],
            }
        },
    }

    res = _client().search(index=index_name, body=body)
    hits = (res or {}).get("hits", {}).get("hits", []) or []

    out: List[RetrievedChunk] = []
    for h in hits:
        score = float(h.get("_score") or 0.0)
        if score < float(min_score):
            continue

        src = (h.get("_source") or {})
        out.append(
            RetrievedChunk(
                source_id=str(src.get(FIELD_SOURCE, "")),
                title=str(src.get(FIELD_TITLE, ""))[:255],
                content=str(src.get(FIELD_CONTENT, "")),
                score=score,
            )
        )
    return out

