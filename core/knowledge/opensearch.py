# backend/core/knowledge/opensearch.py

from typing import List
from django.conf import settings
from opensearchpy import OpenSearch, helpers

from core.knowledge.opensearch_setup import ensure_kb_index


def _client() -> OpenSearch:
    host = getattr(settings, "OPENSEARCH_HOST", "http://localhost:9200")
    timeout = int(getattr(settings, "OPENSEARCH_TIMEOUT", 15))
    return OpenSearch(hosts=[host], timeout=timeout)


def _index_name() -> str:
    return getattr(settings, "OPENSEARCH_KB_INDEX", "kb_chunks_v1")


def bulk_index_chunks(
    *,
    tenant_id: str,
    source_id: str,
    title: str,
    chunks: List[str],
) -> int:
    """
    Bulk index knowledge chunks into kb_chunks_v1.
    Idempotent per (tenant_id, source_id).
    """
    ensure_kb_index()

    client = _client()
    index = _index_name()

    actions = []
    for i, content in enumerate(chunks):
        text = (content or "").strip()
        if not text:
            continue

        doc_id = f"{tenant_id}:{source_id}:{i}"
        actions.append(
            {
                "_op_type": "index",
                "_index": index,
                "_id": doc_id,
                "_source": {
                    "tenant_id": tenant_id,
                    "source_id": source_id,
                    "title": (title or "")[:255],
                    "content": text,
                },
            }
        )

    if not actions:
        return 0

    helpers.bulk(client, actions, refresh="wait_for")
    return len(actions)


def delete_by_source(*, tenant_id: str, source_id: str) -> int:
    """
    Delete all chunks for a given tenant+source_id.
    Used during reprocessing or deletion.
    """
    ensure_kb_index()

    client = _client()
    index = _index_name()

    query = {
        "query": {
            "bool": {
                "filter": [
                    {"term": {"tenant_id": tenant_id}},
                    {"term": {"source_id": source_id}},
                ]
            }
        }
    }

    res = client.delete_by_query(
        index=index,
        body=query,
        refresh=True,
        conflicts="proceed",
    )
    return int((res or {}).get("deleted") or 0)
