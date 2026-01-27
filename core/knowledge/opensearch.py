import uuid
from datetime import datetime, timezone as tz

from django.conf import settings
from opensearchpy import OpenSearch, helpers


def get_client() -> OpenSearch:
    return OpenSearch(settings.OPENSEARCH_URL)


def documents_index_name() -> str:
    return f"{settings.OPENSEARCH_INDEX_PREFIX}-documents"


def bulk_index_chunks(*, tenant_id: str, source_id: str, title: str, chunks: list[str]) -> int:
    if not chunks:
        return 0

    client = get_client()
    index_name = documents_index_name()

    now = datetime.now(tz=tz.utc).isoformat()
    actions = []

    for idx, content in enumerate(chunks):
        doc_id = str(uuid.uuid4())
        actions.append(
            {
                "_op_type": "index",
                "_index": index_name,
                "_id": doc_id,
                "_source": {
                    "tenant_id": str(tenant_id),
                    "source_id": str(source_id),
                    "chunk_index": idx,
                    "title": title or "",
                    "content": content,
                    "created_at": now,
                },
            }
        )

    helpers.bulk(client, actions)
    return len(actions)


def delete_by_source(*, tenant_id: str, source_id: str) -> None:
    client = get_client()
    index_name = documents_index_name()

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
    client.delete_by_query(index=index_name, body=query, refresh=True, conflicts="proceed")
