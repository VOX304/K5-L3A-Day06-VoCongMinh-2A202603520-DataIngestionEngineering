"""Verify saved real run artifacts without rerunning inference or changing labels.

Also assemble explicitly AI-authored review proposals and a human review packet.
Run from root: python starter/scripts/verify_lab06.py --test-run test-<timestamp>
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from starter.src.evaluation import canonical, evaluate_query, summarize
from starter.src.ingestion import load_corpus
from starter.src.run import fingerprints, validate_benchmark, write_json
from starter.src.store import QdrantVectorStore
from starter.scripts.prepare_corpus import SOURCE_SHA256, source_units


def read(path: str | Path):
    return json.loads((ROOT / path).read_text(encoding='utf-8'))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--test-run', required=True, help='Completed test directory name under results/')
    args = parser.parse_args()
    config = read('starter/config.json')
    selection = read('results/selection.json')
    current = fingerprints(ROOT / 'starter/config.json', config)
    require(selection['fingerprints'] == current == read('benchmark/freeze.json')['fingerprints'],
            'Frozen code/config/corpus/benchmark changed')
    raw = ROOT / 'data/raw/alice.txt'
    require(hashlib.sha256(raw.read_bytes()).hexdigest() == SOURCE_SHA256, 'Source bytes changed')
    pages = load_corpus(ROOT / config['corpus'])
    require([asdict(p) for p in source_units(raw.read_text(encoding='utf-8-sig'))] ==
            [asdict(p) for p in pages], 'Prepared corpus does not reproduce from source')
    require(len({canonical(p.text) for p in pages}) == len(pages), 'Duplicate source units')
    manifest = read('data/manifest.json')
    require(manifest['content_units'] == len(pages) and manifest['units'] ==
            [{'page': p.page, **p.metadata} for p in pages], 'Manifest disagrees with corpus')
    questions = read(config['benchmark'])
    validate_benchmark(questions, pages)
    source_review = read('benchmark/source_review.json')
    require(source_review['benchmark_sha256'] == current['benchmark'], 'Answer review is stale')
    require(read('benchmark/freeze.json')['source_review_sha256'] == hashlib.sha256(
        (ROOT / 'benchmark/source_review.json').read_bytes()).hexdigest(), 'Source review changed after freeze')
    require({q['id'] for q in source_review['questions'] if q['answer_supported']} ==
            {q['id'] for q in questions}, 'Incomplete source/answer review')
    locations = {(p.document_id, p.page): p for p in pages}
    by_id = {q['id']: q for q in questions}
    active = {'dev': selection['dev_run'], 'test': args.test_run}
    automated_metadata = Counter()
    runs = {}
    for split, name in active.items():
        run = read(f'results/{name}/run.json')
        require(run['split'] == split and run['fingerprints'] == current, f'{name}: stale run')
        traces = read(f'results/{name}/traces.json')
        expected = {(q['id'], s) for q in questions if q['split'] == split for s in config['strategies']}
        require(len(traces) == len(expected) and {(t['id'], t['strategy']) for t in traces} == expected,
                f'{name}: missing/duplicated trace')
        for trace in traces:
            require(len(trace['hits']) == 3, f'{name}/{trace["id"]}: missing top-3')
            recomputed = evaluate_query(by_id[trace['id']], trace['hits'])
            for key, value in recomputed.items():
                require(trace[key] == value, f'{name}/{trace["id"]}: incorrect {key}')
            scores = [h['score'] for h in trace['hits']]
            require(all(math.isfinite(v) for v in scores) and scores == sorted(scores, reverse=True),
                    'Invalid score/rank order')
            for hit in trace['hits']:
                md = hit['metadata']
                page = locations.get((md.get('document_id'), md.get('page')))
                require(page is not None, 'Unknown source location')
                require(md == {**page.metadata, 'document_id': page.document_id,
                               'source': page.source, 'page': page.page}, 'Incorrect/incomplete metadata')
                require(canonical(hit['text']) in canonical(page.text), 'Chunk not found in claimed source unit')
                if split == 'test':
                    automated_metadata[trace['strategy']] += 1
        metrics = read(f'results/{name}/metrics.json')
        require(summarize(traces) == metrics, f'{name}: metrics disagree with traces')
        runs[split] = {'directory': name, 'metrics': metrics, 'trace_count': len(traces),
                       'elapsed_seconds': run['elapsed_seconds']}
    require(read('benchmark/freeze.json')['frozen_at_utc'] <= selection['selected_at'] <=
            read(f'results/{active["dev"]}/run.json')['timestamp_utc'] <
            read(f'results/{active["test"]}/run.json')['timestamp_utc'], 'Selection chronology invalid')
    stats = read(f'results/{active["dev"]}/chunk_statistics.json')
    metrics = runs['dev']['metrics']
    best = max(config['strategies'], key=lambda s: (metrics[f'{s}/dev']['hit_at_3']['rate'],
               metrics[f'{s}/dev']['hit_at_1']['rate'], -stats[s]['chunk_count']))
    require(best == selection['strategy'], 'Selection does not follow predeclared dev rule')
    model = read('results/model-artifacts.json')
    model_dir = ROOT / config['model_cache'] / 'models--Qdrant--bge-small-en-v1.5-onnx-Q' / 'snapshots' / model['revision']
    for name, digest in model['files_sha256'].items():
        require(hashlib.sha256((model_dir / name).read_bytes()).hexdigest() == digest, 'Model file changed')
    with QdrantVectorStore(ROOT / config['store_path'], 384) as store:
        snapshots = {}
        for strategy in config['strategies']:
            require(store.count(strategy) == stats[strategy]['chunk_count'], 'Re-ingestion/index count mismatch')
            digest = store.snapshot_digest(strategy)
            require(digest == selection['index_fingerprints'][strategy], 'Persisted snapshot changed')
            snapshots[strategy] = digest
        # Compare full B/C payloads and original persisted vectors, ignoring strategy-specific point IDs.
        points = {}
        for strategy in ('B', 'C'):
            records, offset = [], None
            while True:
                batch, offset = store._client.scroll(store._collection(strategy), offset=offset,
                    limit=256, with_payload=True, with_vectors=True)
                records.extend({'payload': p.payload, 'vector': p.vector} for p in batch)
                if offset is None:
                    break
            points[strategy] = sorted(records, key=lambda r: r['payload']['chunk_id'])
        require(points['B'] == points['C'], 'B/C chunks or embeddings differ')

    # Human fields remain untouched. AI proposals live in separate files.
    test_dir = ROOT / 'results' / active['test']
    decisions = read('results/ai-review-decisions.json')
    grounding = {(r['strategy'], r['id']): r for r in decisions['grounding']}
    audit = read(test_dir / 'test_review.json')
    coherent = read(test_dir / 'coherence_review.json')
    proposals, coherence_proposals = [], []
    for row in audit:
        decision = grounding[(row['strategy'], row['id'])]
        proposals.append({**row, 'grounding_score': decision['score'], 'reason': decision['reason'],
            'reviewer': decisions['reviewer'], 'status': 'ai-proposal; pending-human-review',
            'human_reviewed': False})
    b_chunks = {r['source_position'][1]: r['chunk'] for r in coherent if r['strategy'] == 'B'}
    for row in coherent:
        unit = row['source_position'][1]
        if row['strategy'] == 'C':
            require(row['chunk'] == b_chunks[unit], 'B/C coherence samples differ')
        decision = decisions['coherence']['B' if row['strategy'] == 'C' else row['strategy']][unit - 1]
        coherence_proposals.append({**row, **decision, 'reviewer': decisions['reviewer'],
            'status': 'ai-proposal; pending-human-review', 'human_reviewed': False})
    write_json(test_dir / 'ai_test_review.json', proposals)
    write_json(test_dir / 'ai_coherence_review.json', coherence_proposals)
    review_summary = {'provenance': decisions['method'], 'human_test_rows_complete': sum(
        r['status'] == 'human-reviewed' and r['grounding_score'] in (0, 1, 2) and
        bool(r['reviewer']) and bool(r['reason']) and all(
            isinstance(c['complete_and_correct'], bool) and bool(c['reason']) for c in r['metadata_checks'])
        for r in audit), 'human_test_rows_required': len(audit),
        'human_coherence_rows_complete': sum(r['status'] == 'human-reviewed' and r['score'] in (0, 1, 2)
            and bool(r['reviewer']) and bool(r['reason']) for r in coherent),
        'human_coherence_rows_required': len(coherent), 'strategies': {}}
    for strategy in config['strategies']:
        scores = [r['grounding_score'] for r in proposals if r['strategy'] == strategy]
        coherences = [r['score'] for r in coherence_proposals if r['strategy'] == strategy]
        review_summary['strategies'][strategy] = {
            'metadata_automatic_correct': automated_metadata[strategy], 'metadata_automatic_total': 15,
            'ai_coherence_distribution': dict(Counter(coherences)), 'ai_coherence_mean': sum(coherences) / len(coherences),
            'ai_grounding_distribution': {str(i): scores.count(i) for i in (0, 1, 2)},
            'ai_grounding_mean': sum(scores) / len(scores)}
    write_json(test_dir / 'review_summary.json', review_summary)
    lines = ['# Human review packet', '', '**All proposed labels below were written by AI. Human review is pending.**', '',
        'See data/NOTICE.md and data/LICENSE.gutenberg.txt for source terms. The raw source is data/raw/alice.txt.', '',
        'Edit coherence_review.json and test_review.json only after reading each case. Enter actual reviewer, score, reason, '
        'per-hit metadata correctness and status human-reviewed. AI files are separate and do not count as human labels.', '',
        'Rubrics from GUIDE.md: coherence 0=cut/missing context prevents understanding, 1=partially understandable, '
        '2=self-contained complete idea. Grounding 0=no evidence, 1=partial evidence/missing necessary context, '
        '2=enough to answer and trace the source. Metadata correctness is separate from retrieval relevance.', '']
    for row in coherence_proposals:
        lines += [f'## Coherence {row["strategy"]}, source unit {row["source_position"][1]}, position 0', '',
            f'AI proposal: {row["score"]}/2. {row["reason"]}', '', '```text', row['chunk']['text'], '```', '']
    for row in proposals:
        q = by_id[row['id']]
        lines += [f'## Grounding {row["strategy"]}, {row["id"]}', '', q['question'], '',
            f'Expected answer: {q["expected_answer"]}', '', f'AI proposal: {row["grounding_score"]}/2. {row["reason"]}', '']
        for rank, hit in enumerate(row['hits'], 1):
            lines += [f'Rank {rank}; {hit["chunk_id"]}; metadata: {json.dumps(hit["metadata"])}', '',
                      '```text', hit['text'], '```', '']
    # Trim presentation-only trailing whitespace; exact chunk text stays in JSON.
    (test_dir / 'HUMAN_REVIEW.md').write_text('\n'.join(line.rstrip() for line in lines), encoding='utf-8')
    write_json(ROOT / 'results/latest.json', active)
    result = {'checked_at_utc': datetime.now(timezone.utc).isoformat(), 'status': 'passed-technical-verification',
        'source_units': len(pages), 'questions': len(questions), 'selected_strategy': selection['strategy'],
        'runs': runs, 'index_fingerprints': snapshots, 'b_c_payloads_and_vectors_equal': True,
        'metadata_automatic': dict(automated_metadata),
        'human_audit': 'pending; AI proposals are not human labels',
        'human_test_rows_complete': review_summary['human_test_rows_complete'],
        'human_coherence_rows_complete': review_summary['human_coherence_rows_complete']}
    write_json(ROOT / 'results/artifact-verification.json', result)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
