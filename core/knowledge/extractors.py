import re
import requests
from bs4 import BeautifulSoup
from io import BytesIO

from pypdf import PdfReader
from docx import Document as DocxDocument


def normalize_text(text: str) -> str:
    text = text or ""
    text = text.replace("\x00", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def extract_from_text(input_text: str) -> str:
    return normalize_text(input_text)


def extract_from_url(url: str, timeout_s: int = 20) -> str:
    resp = requests.get(url, timeout=timeout_s, headers={"User-Agent": "chatbotbuilder/1.0"})
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    text = soup.get_text(separator=" ")
    return normalize_text(text)


def extract_from_pdf_bytes(data: bytes) -> str:
    reader = PdfReader(BytesIO(data))
    pages = [(p.extract_text() or "") for p in reader.pages]
    return normalize_text(" ".join(pages))


def extract_from_docx_bytes(data: bytes) -> str:
    doc = DocxDocument(BytesIO(data))
    parts = [p.text for p in doc.paragraphs if p.text]
    return normalize_text(" ".join(parts))


def extract_from_plaintext_bytes(data: bytes) -> str:
    try:
        return normalize_text(data.decode("utf-8", errors="ignore"))
    except Exception:
        return ""


def chunk_text(text: str, max_chars: int = 1200, overlap: int = 150) -> list[str]:
    text = normalize_text(text)
    if not text:
        return []
    chunks: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        end = min(i + max_chars, n)
        chunks.append(text[i:end])
        if end == n:
            break
        i = max(0, end - overlap)
    return chunks
