from __future__ import annotations

from typing import List


def chunk_text(text: str, *, chunk_size: int = 900, overlap: int = 120) -> List[str]:
    """
    Very simple char-based chunking.
    - chunk_size: approx characters
    - overlap: repeated chars between chunks
    """
    t = (text or "").strip()
    if not t:
        return []

    if chunk_size <= 0:
        return [t]

    overlap = max(0, min(overlap, chunk_size - 1))
    out: List[str] = []

    start = 0
    n = len(t)
    while start < n:
        end = min(n, start + chunk_size)
        out.append(t[start:end])
        if end >= n:
            break
        start = end - overlap

    return out
