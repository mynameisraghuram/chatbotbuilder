import hashlib
import secrets


def generate_raw_key() -> str:
    return "cb_live_" + secrets.token_urlsafe(32)


def hash_key(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def key_prefix(raw: str) -> str:
    return (raw or "")[:10]
