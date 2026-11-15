"""Read and normalize source data. TODO: implement functions."""
import json
import re
import unicodedata
from pathlib import Path
from .models import DocumentPage


def load_pdf(path: Path, document_id: str, source: str) -> list[DocumentPage]:
    """TODO: extract each physical page; keep its page number and source.

    Detect and record pages with no text. OCR, when needed, is a separate step.
    """
    from pypdf import PdfReader
    pages = []
    for number, page in enumerate(PdfReader(path).pages, 1):
        text = normalize_text(page.extract_text() or '')
        pages.append(DocumentPage(document_id, source, number, text,
                                  {'extraction_status': 'ok' if text else 'empty'}))
    return pages


def normalize_text(text: str) -> str:
    """TODO: normalize Unicode and whitespace without discarding useful structure."""
    text = unicodedata.normalize('NFC', text).replace('\r\n', '\n').replace('\r', '\n')
    lines = [re.sub(r'[^\S\n]+', ' ', line).strip() for line in text.split('\n')]
    return re.sub(r'\n{3,}', '\n\n', '\n'.join(lines)).strip()


def load_corpus(path: Path) -> list[DocumentPage]:
    """Load prepared, provenance-preserving JSONL units; reject duplicate locations."""
    pages: list[DocumentPage] = []
    locations: set[tuple[str, int]] = set()
    for line in path.read_text(encoding='utf-8').splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        page = DocumentPage(**item)
        page.text = normalize_text(page.text)
        key = (page.document_id, page.page)
        if key in locations:
            raise ValueError(f'Duplicate source location: {key}')
        if not page.document_id or not page.source or page.page < 1 or not page.text:
            raise ValueError(f'Invalid source unit: {key}')
        locations.add(key)
        pages.append(page)
    if not pages:
        raise ValueError('Corpus is empty')
    return pages
