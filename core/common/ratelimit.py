import time
import redis
from dataclasses import dataclass
from django.conf import settings


@dataclass
class RateLimitExceeded(Exception):
    retry_after_seconds: int


def _redis():
    return redis.Redis.from_url(getattr(settings, "REDIS_URL", "redis://127.0.0.1:6379/0"), decode_responses=True)


def rate_limit_or_raise(*, key: str, limit: int, window_seconds: int) -> None:
    """
    Fixed window rate limit using INCR + EXPIRE.
    key should already include bucket (minute or window).
    """
    r = _redis()
    pipe = r.pipeline()
    pipe.incr(key, 1)
    pipe.ttl(key)
    count, ttl = pipe.execute()

    if ttl == -1:
        r.expire(key, window_seconds)
        ttl = window_seconds

    if int(count) > int(limit):
        retry = int(ttl if ttl and ttl > 0 else window_seconds)
        raise RateLimitExceeded(retry_after_seconds=retry)
