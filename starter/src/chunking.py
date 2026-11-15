"""Implement fixed-size and structure-aware chunking."""
import hashlib
import re
from .models import Chunk, DocumentPage


def _chunk(page: DocumentPage, text: str, start: int, method: str) -> Chunk:
    identity = f'{page.document_id}:{page.page}:{method}:{start}:{text}'
    chunk_id = hashlib.sha256(identity.encode()).hexdigest()[:32]
    return Chunk(chunk_id, page.document_id, page.source, page.page, text, dict(page.metadata))


def fixed_size(page: DocumentPage, size: int, overlap: int) -> list[Chunk]:
    """TODO: split text into overlapping windows and retain page metadata."""
    if size <= 0 or not 0 <= overlap < size:
        raise ValueError('Require size > 0 and 0 <= overlap < size')
    chunks = []
    for start in range(0, len(page.text), size - overlap):
        text = page.text[start:start + size]
        if text.strip():
            chunks.append(_chunk(page, text, start, f'fixed-{size}-{overlap}'))
        if start + size >= len(page.text):
            break
    return chunks


def by_paragraph(page: DocumentPage, max_size: int) -> list[Chunk]:
    """TODO: group paragraphs, split oversized paragraphs and retain metadata."""
    if max_size <= 0:
        raise ValueError('max_size must be positive')
    chunks = []
    pending = ''
    start = 0
    for match in re.finditer(r'\S[\s\S]*?(?=\n\s*\n|\Z)', page.text):
        paragraph = match.group().strip()
        if pending and len(pending) + 2 + len(paragraph) > max_size:
            chunks.append(_chunk(page, pending, start, f'paragraph-{max_size}'))
            pending = ''
        if len(paragraph) > max_size:
            for offset in range(0, len(paragraph), max_size):
                chunks.append(_chunk(page, paragraph[offset:offset + max_size],
                                     match.start() + offset, f'paragraph-{max_size}'))
        else:
            if not pending:
                start = match.start()
            pending = pending + '\n\n' + paragraph if pending else paragraph
    if pending:
        chunks.append(_chunk(page, pending, start, f'paragraph-{max_size}'))
    return chunks
