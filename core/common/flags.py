import json
import redis
from django.conf import settings
from django.db import transaction

from core.flags.models import FeatureFlag, TenantFeatureFlag

def _redis():
    try:
        return redis.from_url(settings.REDIS_URL, decode_responses=True, socket_connect_timeout=1, socket_timeout=1)
    except Exception:
        return None

def _cache_key(tenant_id: str) -> str:
    return f"ff:{tenant_id}"

def get_entitlements(tenant_id: str) -> dict:
    r = _redis()
    ck = _cache_key(tenant_id)

    if r:
        try:
            cached = r.get(ck)
            if cached:
                return json.loads(cached)
        except Exception:
            pass

    # DB source of truth
    global_flags = {f.key: f.enabled_by_default for f in FeatureFlag.objects.all()}
    overrides = TenantFeatureFlag.objects.filter(tenant_id=tenant_id).select_related("key")
    for o in overrides:
        global_flags[o.key.key] = o.is_enabled

    if r:
        try:
            r.setex(ck, 300, json.dumps(global_flags))
        except Exception:
            pass

    return global_flags

def is_enabled(tenant_id: str, key: str) -> bool:
    return bool(get_entitlements(tenant_id).get(key, False))

def bust_cache(tenant_id: str) -> None:
    r = _redis()
    if not r:
        return
    try:
        r.delete(_cache_key(tenant_id))
    except Exception:
        return
