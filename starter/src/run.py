"""Run real A/B/C experiments: python -m starter.src.run --split dev (then test)."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import platform
import sys
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .chunking import by_paragraph, fixed_size
from .embeddings import MyEmbedder
from .evaluation import canonical, evaluate_query, summarize
from .ingestion import load_corpus
from .models import DocumentPage
from .store import QdrantVectorStore

ROOT = Path(__file__).resolve().parents[2]


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def validate_benchmark(questions: list[dict[str, Any]], pages: list[DocumentPage]) -> None:
    if len({q['id'] for q in questions}) != len(questions):
        raise ValueError('Duplicate question IDs')
    if any(q['split'] not in ('dev', 'test') for q in questions):
        raise ValueError('Only dev/test splits allowed')
    for split, minimum in [('dev', 15), ('test', 5)]:
        if sum(q['split'] == split for q in questions) < minimum:
            raise ValueError(f'Need at least {minimum} {split} questions')
    filtered = [q for q in questions if q.get('filter')]
    if len(filtered) < 3 or not any(q['split'] == 'test' for q in filtered):
        raise ValueError('Need >=3 filtered questions including >=1 test')
    locations = {(p.document_id, p.page): p for p in pages}
    for q in questions:
        if not q['question'].strip() or not q['expected_answer'].strip() or not canonical(q['evidence_quote']):
            raise ValueError(f"Empty benchmark field: {q['id']}")
        for gold in [{'source_id': q['gold_source_id'], 'page': q['gold_page'], 'quote': q['evidence_quote']},
                     *q.get('alternative_evidence', [])]:
            page = locations.get((gold['source_id'], gold['page']))
            if page is None or not canonical(gold['quote']) or canonical(gold['quote']) not in canonical(page.text):
                raise ValueError(f"Unverified evidence: {q['id']}")
        for key, value in q.get('filter', {}).items():
            if key in ('document_id', 'source', 'page', 'gold_source_id', 'gold_page', 'expected_answer'):
                raise ValueError('Use contextual metadata filters, not gold location')
            values = {p.metadata.get(key) for p in pages}
            if value not in values or len(values - {None}) < 2:
                raise ValueError(f"Filter lacks contrasting source scopes: {q['id']}/{key}")
            if locations[(q['gold_source_id'], q['gold_page'])].metadata.get(key) != value:
                raise ValueError(f"Filter contradicts evidence: {q['id']}")


def fingerprints(config_path: Path, config: dict[str, Any]) -> dict[str, str]:
    paths = {'config': config_path, 'corpus': ROOT / config['corpus'], 'benchmark': ROOT / config['benchmark']}
    paths.update({f'code/{p.name}': p for p in Path(__file__).parent.glob('*.py')})
    return {key: hashlib.sha256(path.read_bytes()).hexdigest() for key, path in paths.items()}


def execute(config_path: Path, split: str) -> Path:
    config = json.loads(config_path.read_text(encoding='utf-8'))
    pages = load_corpus(ROOT / config['corpus'])
    if len(pages) < 30 or any(len(p.text) < 1500 for p in pages):
        raise ValueError('Prepared unpaginated corpus needs >=30 units of >=1500 normalized characters')
    if len({canonical(p.text) for p in pages}) != len(pages):
        raise ValueError('Duplicated corpus units are not allowed')
    questions = json.loads((ROOT / config['benchmark']).read_text(encoding='utf-8'))
    validate_benchmark(questions, pages)
    digest = fingerprints(config_path, config)
    selection_path = ROOT / 'results/selection.json'
    if split == 'test':
        selection = json.loads(selection_path.read_text(encoding='utf-8'))
        if selection['fingerprints'] != digest:
            raise ValueError('Code/data/config changed since dev selection. Record change and rerun dev; avoid test tuning.')
    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    output = ROOT / 'results' / f'{split}-{run_id}'
    output.mkdir(parents=True)
    started = time.perf_counter()
    embedder = MyEmbedder(config['model'], cache_dir=ROOT / config['model_cache'])
    traces: list[dict[str, Any]] = []
    stats: dict[str, Any] = {}
    snapshot_hashes: dict[str, str] = {}
    coherent: list[dict[str, Any]] = []
    try:
        with QdrantVectorStore(ROOT / config['store_path'], embedder.dimensions) as store:
            vectors_by_text: dict[tuple[str, ...], list[list[float]]] = {}
            for strategy, options in config['strategies'].items():
                tick = time.perf_counter()
                chunks = [c for p in pages for c in (
                    fixed_size(p, options['size'], options.get('overlap', 0))
                    if options['chunking'] == 'fixed' else by_paragraph(p, options['size']))]
                if split == 'dev':
                    texts = tuple(c.text for c in chunks)
                    if texts not in vectors_by_text:
                        vectors_by_text[texts] = embedder.embed_documents(list(texts))
                    store.upsert(strategy, chunks, vectors_by_text[texts])
                    store.upsert(strategy, chunks, vectors_by_text[texts])
                if store.count(strategy) != len(chunks):
                    raise ValueError('Index count mismatch or missing frozen index')
                snapshot_hashes[strategy] = store.snapshot_digest(strategy)
                if split == 'test' and snapshot_hashes[strategy] != selection['index_fingerprints'][strategy]:
                    raise ValueError('Persisted vector snapshot changed after dev selection')
                lengths = sorted(len(c.text) for c in chunks)
                stats[strategy] = {'chunk_count': len(chunks), 'characters': sum(lengths),
                                   'min_chars': min(lengths), 'median_chars': lengths[len(lengths) // 2],
                                   'max_chars': max(lengths), 'ingest_and_reingest_seconds': time.perf_counter() - tick,
                                   'index_reused': split == 'test'}
                for p in pages[:10]:
                    chunk = next(c for c in chunks if c.page == p.page and c.document_id == p.document_id)
                    coherent.append({'strategy': strategy, 'source_position': [p.document_id, p.page, 0],
                                     'chunk': asdict(chunk), 'score': None, 'reason': '', 'reviewer': '',
                                     'status': 'pending-human-review'})
            for question in [q for q in questions if q['split'] == split]:
                query = embedder.embed_query(question['question'])
                for strategy, options in config['strategies'].items():
                    tick = time.perf_counter()
                    hits = store.search(strategy, query, top_k=3,
                                        filters=question.get('filter') if options['filter'] else None)
                    trace = evaluate_query(question, hits)
                    trace.update(strategy=strategy, filter_applied=bool(options['filter'] and question.get('filter')),
                                 retrieval_seconds=time.perf_counter() - tick)
                    traces.append(trace)
        metrics = summarize(traces)
        if split == 'dev':
            best = max(config['strategies'], key=lambda s: (metrics[f'{s}/dev']['hit_at_3']['rate'],
                        metrics[f'{s}/dev']['hit_at_1']['rate'], -stats[s]['chunk_count']))
            write_json(selection_path, {'strategy': best, 'rule': config['selection_rule'],
                                        'fingerprints': digest, 'index_fingerprints': snapshot_hashes,
                                        'dev_run': output.name,
                                        'selected_at': datetime.now(timezone.utc).isoformat()})
        write_json(output / 'metrics.json', metrics)
        write_json(output / 'traces.json', traces)
        write_json(output / 'chunk_statistics.json', stats)
        write_json(output / 'coherence_review.json', coherent)
        if split == 'test':
            locations = {(p.document_id, p.page): p for p in pages}
            audit = []
            for trace in traces:
                checks = []
                for hit in trace['hits']:
                    md = hit['metadata']
                    page = locations.get((md.get('document_id'), md.get('page')))
                    checks.append({'chunk_id': hit['chunk_id'], 'retrieved': md,
                                   'source_unit_exists': page is not None,
                                   'expected_metadata': {**page.metadata, 'source': page.source} if page else None,
                                   'complete_and_correct': None, 'reason': ''})
                audit.append({'id': trace['id'], 'strategy': trace['strategy'], 'hits': trace['hits'],
                              'metadata_checks': checks, 'grounding_score': None,
                              'reason': '', 'reviewer': '', 'status': 'pending-human-review'})
            write_json(output / 'test_review.json', audit)
        versions = {name: importlib.metadata.version(name) for name in (
            'fastembed', 'qdrant-client', 'numpy', 'onnxruntime', 'tokenizers', 'huggingface-hub')}
        write_json(output / 'run.json', {'status': 'completed-retrieval; human audit pending',
                    'split': split, 'config': config, 'fingerprints': digest, 'versions': versions,
                    'python': platform.python_version(), 'elapsed_seconds': time.perf_counter() - started,
                    'api_cost_usd': 0, 'cost_note': 'Local CPU inference; electricity/hardware not priced',
                    'model': embedder.model_name, 'dimensions': embedder.dimensions,
                    'embedding_method': 'FastEmbed embed(documents) and query_embed(question); no additional text prefix; CPUExecutionProvider',
                    'timestamp_utc': datetime.now(timezone.utc).isoformat()})
    except Exception as exc:
        write_json(output / 'failure.json', {'status': 'failed', 'error_type': type(exc).__name__,
                                           'error': str(exc), 'split': split, 'fingerprints': digest})
        raise
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=ROOT / 'starter/config.json')
    parser.add_argument('--split', choices=['dev', 'test'], required=True)
    args = parser.parse_args()
    try:
        print(execute(args.config.resolve(), args.split))
    except Exception as exc:
        write_json(ROOT / 'results/last_failure.json', {
            'timestamp_utc': datetime.now(timezone.utc).isoformat(),
            'split': args.split, 'error_type': type(exc).__name__, 'error': str(exc)})
        print(f'Experiment not completed: {type(exc).__name__}: {exc}', file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
