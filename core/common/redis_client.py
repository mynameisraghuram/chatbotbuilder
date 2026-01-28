from django.conf import settings

import redis


def get_redis():
    """
    Uses settings.REDIS_URL if present, else defaults to localhost.
    Keep this tiny and predictable.
    """
    url = getattr(settings, "REDIS_URL", None) or "redis://localhost:6379/0"
    return redis.from_url(url, decode_responses=True)
