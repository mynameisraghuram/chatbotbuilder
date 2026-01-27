import re
import requests
from bs4 import BeautifulSoup

try:
    from pypdf import PdfReader
except Exception:
    PdfReader = None


def normalize_text(text: str) -> str:
    text = text or ""
    text = text.replace("\x00", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def extract_from_text(input_text: str) -> str:
    return normalize_text(input_text)


def extract_from_url(url: str, timeout_s: int = 20) -> str:
    resp = requests.get(url, timeout=timeout_s, headers={"User-Agent": "chatbuilderbot/1.0"})
    resp.raise_for_status()
    html = resp.text
    soup = BeautifulSoup(html, "html.parser")

    # remove scripts/styles
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    text = soup.get_text(separator=" ")
    return normalize_text(text)


def extract_from_pdf_file(path: str) -> str:
    if PdfReader is None:
        raise RuntimeError("pypdf not installed; cannot parse PDFs")

    reader = PdfReader(path)
    pages = []
    for p in reader.pages:
        pages.append(p.extract_text() or "")
    return normalize_text(" ".join(pages))


def chunk_text(text: str, max_chars: int = 1200, overlap: int = 150) -> list[str]:
    text = normalize_text(text)
    if not text:
        return []

    chunks = []
    i = 0
    n = len(text)

    while i < n:
        end = min(i + max_chars, n)
        chunk = text[i:end]
        chunks.append(chunk)
        if end == n:
            break
        i = max(0, end - overlap)

    return chunks
