"""Fetch Gutenberg #11, prepare source units, and VERIFY candidate gold evidence.

Run from repository root: python starter/scripts/prepare_corpus.py
The candidate file is never treated as a validated benchmark automatically.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import urllib.request
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from starter.src.ingestion import normalize_text
from starter.src.evaluation import canonical
from starter.src.models import DocumentPage

SOURCE = 'https://www.gutenberg.org/ebooks/11.txt.utf-8'
SOURCE_SHA256 = '01b38ea4c710a84bc18d0bd41271a5a1a92b94e97b2812f4dece97d4a694725e'


def source_units(text: str, minimum: int = 1500) -> list[DocumentPage]:
    """Sequential source units, not artificial duplicates or retrieval chunks."""
    if minimum < 1500:
        raise ValueError('Unpaginated source units need >=1500 normalized characters')
    end = re.search(r'\*\*\* END OF (?:THE|THIS) PROJECT GUTENBERG', text, re.I)
    body = text[:end.start()] if end else text
    headings = list(re.finditer(r'^CHAPTER\s+([IVXLCDM]+)\.[^\n]*', body, re.M))
    # Some editions repeat chapter headings in the table of contents.
    last = {m.group(1): m for m in headings}
    headings = sorted(last.values(), key=lambda m: m.start())
    if len(headings) != 12:
        raise ValueError(f'Expected 12 body chapter headings; found {len(headings)}. Inspect source edition.')
    pages: list[DocumentPage] = []
    for i, heading in enumerate(headings):
        stop = headings[i + 1].start() if i + 1 < len(headings) else len(body)
        chapter = normalize_text(body[heading.start():stop].replace('_', ''))
        pieces = []
        pending = ''
        for paragraph in chapter.split('\n\n'):
            pending = pending + '\n\n' + paragraph if pending else paragraph
            if len(pending) >= minimum:
                pieces.append(pending)
                pending = ''
        if pending:
            if not pieces:
                raise ValueError('Chapter shorter than source-unit minimum')
            pieces[-1] += '\n\n' + pending
        offset = 0
        for piece in pieces:
            pages.append(DocumentPage('gutenberg-11', SOURCE, len(pages) + 1, piece,
                                      {'chapter_roman': heading.group(1), 'language': 'en',
                                       'unit_chars': len(piece), 'chapter_char_start': offset,
                                       'chapter_char_end': offset + len(piece)}))
            offset += len(piece) + 2
    if len(pages) < 30:
        raise ValueError(f'Only {len(pages)} source units; >=30 required')
    return pages


def verify_questions(candidates: list[dict], pages: list[DocumentPage]) -> tuple[list[dict], list[dict]]:
    verified, problems = [], []
    for question in candidates:
        matches = [p for p in pages if canonical(question['evidence_quote']) in canonical(p.text)
                   and all(p.metadata.get(k) == v for k, v in question.get('filter', {}).items())]
        if not matches:
            problems.append({'id': question['id'], 'problem': 'Quote not found in claimed scope; verify source manually'})
            continue
        gold = matches[0]
        result = dict(question, gold_source_id=gold.document_id, gold_page=gold.page,
                      evidence_validation='exact normalized containment; answer sufficiency needs human review')
        result['alternative_evidence'] = [dict(source_id=p.document_id, page=p.page,
                                              quote=question['evidence_quote']) for p in matches[1:]]
        verified.append(result)
    return verified, problems


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--local-source', type=Path, help='Use previously downloaded Gutenberg text')
    args = parser.parse_args()
    raw = ROOT / 'data/raw/alice.txt'
    raw.parent.mkdir(parents=True, exist_ok=True)
    if args.local_source:
        raw.write_bytes(args.local_source.read_bytes())
    elif not raw.exists():
        with urllib.request.urlopen(SOURCE, timeout=60) as response:
            raw.write_bytes(response.read())
    source_hash = hashlib.sha256(raw.read_bytes()).hexdigest()
    if source_hash != SOURCE_SHA256:
        raise SystemExit('Source snapshot differs from the verified edition. Restore the pinned source; '
                         'review and version a new benchmark before using a changed edition.')
    text = raw.read_text(encoding='utf-8-sig')
    pages = source_units(text)
    (ROOT / 'data/corpus.jsonl').write_text('\n'.join(json.dumps(asdict(p), ensure_ascii=False) for p in pages) + '\n', encoding='utf-8')
    manifest = {'source_id': 'gutenberg-11', 'title': "Alice's Adventures in Wonderland",
                'source_path_or_url': SOURCE, 'raw_path': 'data/raw/alice.txt',
                'license_or_permission': 'Original English literary work; author died 1898; public domain in USA per catalog. '
                                         'Vietnam life+50 basis and retained Gutenberg terms: see docs/corpus-choice.md and data/NOTICE.md.',
                'license_path': 'data/LICENSE.gutenberg.txt',
                'accessed_at': datetime.fromtimestamp(raw.stat().st_mtime, timezone.utc).isoformat(),
                'accessed_at_basis': 'Local raw snapshot mtime at download/import; not an edition publication date',
                'edition': 'The Millennium Fulcrum Edition 3.0; Gutenberg update June 26, 2025 (raw header)',
                'sha256': source_hash,
                'unit_rule': 'sequential chapter-local paragraph groups >=1500 NFC characters; short tails merged',
                'normalization': 'NFC; CRLF to LF; strip line edges/collapse horizontal whitespace; preserve paragraph breaks; remove underscore emphasis markers',
                'physical_pages': None, 'content_units': len(pages),
                'total_unit_characters': sum(len(p.text) for p in pages),
                'boundary_convention': 'Chapter-local normalized character offsets [start,end); two newline separators between units are excluded',
                'units': [{'page': p.page, **p.metadata} for p in pages]}
    (ROOT / 'data/manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    (ROOT / 'data/LICENSE.gutenberg.txt').write_text(text[text.index('START: FULL LICENSE'):], encoding='utf-8')
    notice = text[text.index('This eBook is for'):text.index('\nTitle:')].strip()
    (ROOT / 'data/NOTICE.md').write_text(
        '# Source notice\n\n' + notice + '\n\n'
        'Full terms: [Project Gutenberg License](LICENSE.gutenberg.txt), '
        '[online license](https://www.gutenberg.org/policy/license.html).\n\n'
        'Original unmodified source including all notices: [raw/alice.txt](raw/alice.txt).\n'
        'Corpus, benchmark quotes and retrieval traces are normalized excerpts for a local educational experiment; '
        'retain this notice and full license alongside them. Author: Lewis Carroll. '
        'No translation, illustrations or modern editorial commentary are used.\n', encoding='utf-8')
    seeds = json.loads((ROOT / 'benchmark/question_seeds.json').read_text(encoding='utf-8'))['questions']
    questions, problems = verify_questions(seeds, pages)
    destination = ROOT / 'benchmark/questions.json'
    # Invalidate an earlier benchmark when source/seed verification fails.
    if destination.exists():
        destination.unlink()
    (ROOT / 'benchmark/validation.json').write_text(json.dumps({'verified': len(questions), 'problems': problems}, indent=2), encoding='utf-8')
    if problems:
        raise SystemExit(f'{len(problems)} unverified quotes: see benchmark/validation.json. Correct seeds against source; do not invent quotes.')
    destination.write_text(json.dumps(questions, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'{len(pages)} content units, {len(questions)} quotes verified. Review answer sufficiency before experiments.')


if __name__ == '__main__':
    main()
