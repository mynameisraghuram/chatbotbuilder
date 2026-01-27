# repo-root/backend/core/leads/search.py

from typing import Dict, Any, List, Tuple

from django.conf import settings
from opensearchpy import OpenSearch


def _client() -> OpenSearch:
    return OpenSearch(settings.OPENSEARCH_URL)


def _index_name() -> str:
    return f"{settings.OPENSEARCH_INDEX_PREFIX}-leads"


def search_leads_os(*, tenant_id: str, query: str, limit: int, offset: int) -> Tuple[int, List[Dict[str, Any]]]:
    """
    Returns (total, items)
    Each item is the stored document shape from leads/opensearch.py.
    """
    q = (query or "").strip()
    if not q:
        raise ValueError("query is required")

    body = {
        "from": offset,
        "size": limit,
        "track_total_hits": True,
        "query": {
            "bool": {
                "filter": [
                    {"term": {"tenant_id": tenant_id}},
                ],
                "must": [
                    {
                        "multi_match": {
                            "query": q,
                            "fields": ["name^2", "email^2", "phone", "status"],
                            "type": "best_fields",
                            "operator": "and",
                        }
                    }
                ],
            }
        },
        "sort": [{"updated_at": {"order": "desc"}}],
    }

    resp = _client().search(index=_index_name(), body=body)
    total = int(resp["hits"]["total"]["value"])
    hits = resp["hits"]["hits"]
    items = [h["_source"] for h in hits]
    return total, items
