from django.conf import settings
from opensearchpy import OpenSearch


def ensure_kb_index():
    host = getattr(settings, "OPENSEARCH_HOST", "http://localhost:9200")
    index = getattr(settings, "OPENSEARCH_KB_INDEX", "kb_chunks_v1")
    client = OpenSearch(hosts=[host])

    if client.indices.exists(index=index):
        return

    body = {
        "settings": {"index": {"number_of_shards": 1, "number_of_replicas": 0}},
        "mappings": {
            "properties": {
                "tenant_id": {"type": "keyword"},
                "source_id": {"type": "keyword"},
                "title": {"type": "text"},
                "content": {"type": "text"},
            }
        },
    }
    client.indices.create(index=index, body=body)
