"""TODO: evaluate retrieved evidence and preserve per-query traces."""
from typing import Any
from collections import defaultdict
import re
import unicodedata


def canonical(text: str) -> str:
    return re.sub(r'\s+', ' ', unicodedata.normalize('NFC', text)).strip()


def evaluate_query(question: dict[str, Any], hits: list[dict[str, Any]]) -> dict[str, Any]:
    """TODO: check source/page and enough gold evidence; keep hit@1 and hit@3 trace.

    Accept any documented alternative gold evidence. Do not infer human grounding
    or chunk coherence labels from exact string match.
    """
    evidence = [{'source_id': question['gold_source_id'], 'page': question['gold_page'],
                 'quote': question['evidence_quote']}, *question.get('alternative_evidence', [])]
    matched = []
    for hit in hits[:3]:
        metadata = hit['metadata']
        matched.append(any(
            metadata.get('document_id') == gold['source_id']
            and metadata.get('page') == gold['page']
            and bool(canonical(gold['quote']))
            and canonical(gold['quote']) in canonical(hit['text'])
            for gold in evidence))
    filters = question.get('filter', {})
    return {'id': question['id'], 'split': question['split'], 'question': question.get('question'),
            'hit_at_1': bool(matched and matched[0]), 'hit_at_3': any(matched),
            'evidence_matches': matched, 'hits': hits[:3], 'gold_evidence': evidence,
            'filter': filters,
            'filter_compliant': (bool(hits) and all(
                all(h['metadata'].get(k) == v for k, v in filters.items()) for h in hits[:3]
            )) if filters else None,
            'metric_method': 'exact normalized evidence containment + source/unit; conservative proxy'}


def summarize(traces: list[dict[str, Any]]) -> dict[str, Any]:
    """TODO: aggregate Hit@1 and Evidence Hit@3 by strategy and dev/test split."""
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for trace in traces:
        groups[f"{trace['strategy']}/{trace['split']}"].append(trace)
    result: dict[str, Any] = {}
    for name, group in groups.items():
        result[name] = {}
        for metric in ('hit_at_1', 'hit_at_3'):
            correct = sum(bool(t[metric]) for t in group)
            result[name][metric] = {'correct': correct, 'total': len(group), 'rate': correct / len(group)}
        filtered = [t for t in group if t.get('filter')]
        result[name]['filter_compliance'] = {'correct': sum(bool(t['filter_compliant']) for t in filtered),
                                            'total': len(filtered)} if filtered else None
    return result
