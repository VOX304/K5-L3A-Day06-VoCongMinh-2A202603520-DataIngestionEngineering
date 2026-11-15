"""Record actual prerequisites without inventing retrieval results."""
import importlib.util
import json
import socket
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
checks = {}
for name in ('fastembed', 'qdrant_client', 'pypdf', 'pytest', 'mypy'):
    checks[f'module/{name}'] = importlib.util.find_spec(name) is not None
for host in ('pypi.org', 'www.gutenberg.org', 'huggingface.co'):
    try:
        socket.getaddrinfo(host, 443)
        checks[f'dns/{host}'] = True
    except OSError as exc:
        checks[f'dns/{host}'] = {'ok': False, 'error': str(exc)}
for path in ('data/corpus.jsonl', 'data/manifest.json', 'benchmark/questions.json'):
    checks[f'file/{path}'] = (ROOT / path).is_file()
seed = ROOT / 'benchmark/question_seeds.json'
if seed.exists():
    items = json.loads(seed.read_text(encoding='utf-8'))['questions']
    checks['candidate_questions'] = {'dev': sum(q['split'] == 'dev' for q in items),
                                     'test': sum(q['split'] == 'test' for q in items),
                                     'status': 'seeds; quote checks in benchmark/validation.json; answer review in benchmark/source_review.json'}
result = {'timestamp_utc': datetime.now(timezone.utc).isoformat(), 'python': sys.version,
          'checks': checks, 'check_type': 'prerequisites only; retrieval execution is recorded in timestamped run directories'}
destination = ROOT / 'results/environment-check.json'
destination.parent.mkdir(exist_ok=True)
destination.write_text(json.dumps(result, indent=2), encoding='utf-8')
print(json.dumps(result, indent=2))
required = ('module/fastembed', 'module/qdrant_client', 'file/data/corpus.jsonl', 'file/benchmark/questions.json')
raise SystemExit(0 if all(checks.get(k) is True for k in required) else 1)
