from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional

from django.conf import settings
from opensearchpy import OpenSearch, helpers

from core.knowledge.opensearch_setup import ensure_kb_index


@dataclass
class ChunkDoc:
    tenant_id: str
    source_id: str
    title: str
    content: str


def _client() -> OpenSearch:
    host = getattr(settings, "OPENSEARCH_HOST", "http://localhost:9200")
    timeout = int(getattr(settings, "OPENSEARCH_TIMEOUT", 15))
    return OpenSearch(hosts=[host], timeout=timeout)


def _index_name() -> str:
    return getattr(settings, "OPENSEARCH_KB_INDEX", "kb_chunks_v1")


def upsert_chunks(*, chunks: Iterable[ChunkDoc]) -> int:
    """
    Bulk upsert chunk documents into kb index.
    Uses deterministic _id so reprocessing is idempotent:
      _id = "{tenant_id}:{source_id}:{i}"
    """
    ensure_kb_index()
    client = _client()
    index = _index_name()

    actions = []
    count = 0
    for i, c in enumerate(chunks):
        content = (c.content or "").strip()
        if not content:
            continue

        doc_id = f"{c.tenant_id}:{c.source_id}:{i}"
        actions.append(
            {
                "_op_type": "index",
                "_index": index,
                "_id": doc_id,
                "_source": {
                    "tenant_id": c.tenant_id,
                    "source_id": c.source_id,
                    "title": (c.title or "")[:255],
                    "content": content,
                },
            }
        )
        count += 1

    if not actions:
        return 0

    helpers.bulk(client, actions, refresh="wait_for")
    return count


def delete_chunks_for_source(*, tenant_id: str, source_id: str) -> int:
    """
    Delete all chunks for a given tenant+source_id (used for reprocess or delete).
    """
    ensure_kb_index()
    client = _client()
    index = _index_name()

    query = {
        "query": {
            "bool": {
                "filter": [
                    {"term": {"tenant_id": str(tenant_id)}},
                    {"term": {"source_id": str(source_id)}},
                ]
            }
        }
    }

    res = client.delete_by_query(index=index, body=query, refresh=True, conflicts="proceed")
    return int((res or {}).get("deleted") or 0)
