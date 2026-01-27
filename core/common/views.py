from django.http import JsonResponse
from django.db import connection
from django.conf import settings
import redis
from opensearchpy import OpenSearch

def health_check(request):
    status = {"db": False, "redis": False, "opensearch": False}

    # DB
    try:
        with connection.cursor() as c:
            c.execute("SELECT 1")
        status["db"] = True
    except Exception:
        pass

    # Redis
    try:
        r = redis.Redis.from_url(settings.REDIS_URL)
        r.ping()
        status["redis"] = True
    except Exception:
        pass

    # OpenSearch
    try:
        client = OpenSearch(settings.OPENSEARCH_URL)
        client.info()
        status["opensearch"] = True
    except Exception:
        pass

    http_status = 200 if all(status.values()) else 503
    return JsonResponse(status, status=http_status)
