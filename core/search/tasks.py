from celery import shared_task
from core.common.opensearch import get_client

@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={"max_retries": 3})
def opensearch_health_task(self):
    client = get_client()
    return client.info().get("version", {}).get("number", "unknown")
