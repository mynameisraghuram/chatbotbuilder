from django.core.files.base import ContentFile
from django.core.files.storage import default_storage


def upload_bytes(data: bytes, path: str, content_type: str = "application/octet-stream") -> str:
    """
    Upload raw bytes to configured storage and return public URL.
    """
    default_storage.save(path, ContentFile(data))
    try:
        return default_storage.url(path)
    except Exception:
        return path
