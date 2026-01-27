from django.conf import settings
from opensearchpy import OpenSearch

def get_client() -> OpenSearch:
    return OpenSearch(
        hosts=[settings.OPENSEARCH_URL],
        http_compress=True,
        timeout=10,
        max_retries=2,
        retry_on_timeout=True,
    )

def index_name(suffix: str) -> str:
    return f"{settings.OPENSEARCH_INDEX_PREFIX}-{suffix}".lower()
