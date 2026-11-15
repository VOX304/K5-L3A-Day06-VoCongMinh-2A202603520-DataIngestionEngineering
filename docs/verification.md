# Verification record

Base: `42f64eb230289ff5042abc03683252649dfbef79`. Verification continued on 2026-11-15
with working network access. Prior blocked-session records remain in `results/history/`.

- Dependencies installed in `.venv`; `pip check` passes. Exact versions are in
  `starter/requirements-lock.txt` (UTF-8). Python 3.12.2, FastEmbed 0.9.1,
  qdrant-client 1.20.0, ONNX Runtime 1.32.0, NumPy 2.5.4.
- Preflight now passes all required dependency, DNS and input checks.
- Real model smoke check: 384 dimensions and finite, unit-length vector. Model
  repository revision and every downloaded model/tokenizer file hash are recorded
  in `results/model-artifacts.json`. No synthetic fallback was used.
- Corpus preparation: **82** distinct source units, 142,809 characters, min 1,500,
  max 3,092; 20/20 quotes verified. Per-answer source review and freeze precede
  retrieval. Raw source hash and manifest boundaries reproduce exactly.
- `python -m pytest tests -q --junitxml=results/integration-tests.xml`: **20 passed,
  no skipped tests**. This includes real local Qdrant filter/persistence/replacement,
  unchanged reload fingerprint and same-count vector mutation coverage.
- `python -m mypy starter/src --ignore-missing-imports`: passes, 8 source files.
  Three annotation errors exposed after installation were corrected before dev.
- `python -m compileall -q starter/src starter/scripts`: passes.
- Real CLI dev and test both completed. `results/latest.json` identifies the current
  runs. Test reused disk indexes with exact config/code/corpus/benchmark/index hashes.
- `python starter/scripts/verify_lab06.py --test-run test-20261115T041850787763Z`:
  passes source reconstruction, frozen inputs, 60 traces / 180 hit records, metric
  recomputation, all source/text/metadata checks, model hashes, selection chronology,
  persisted snapshot hashes and exact B/C payload/vector equality.
- Human review coverage is **0/30** coherence and **0/15** test rows. AI proposals
  and reasons are separate; they are not claimed as human labels.
- Git whitespace checks pass. Frozen file paths retain their exact bytes through
  `.gitattributes`; CRLF is recognized as a line ending for whitespace checks.
  Unmodified upstream source/license whitespace is intentionally preserved.

## Reload fingerprint defect: actual red/green loop

The first dev run completed (`dev-20261115T041425146041Z`), but test
`test-20261115T041602035125Z` failed with `Persisted vector snapshot changed after
dev selection` before any test queries ran. See its `failure.json` (the directory
name is also discoverable under `results/test-*/failure.json`).

Minimal command: `python -m pytest tests/test_store.py::test_frozen_digest_survives_reload_for_non_axis_vectors -q`.
It failed after upserting `[0.2, 0.3, 0.4]`, closing and reopening: expected unchanged
digest, got different digests. Inspection showed equal ID/payload, but immediate
scroll returned `[0.3713906407, 0.5570859909, 0.7427812815]`, while reload returned
the persisted original `[0.2, 0.3, 0.4]`. The failure was representation drift, not
an index mutation. Qdrant local's installed `local_collection.py` confirmed the
different insert/update and reload paths.

`snapshot_digest` now closes/reopens before reading exact records. Both dev search
and test search therefore use disk-loaded values. No decimal rounding or count-only
check is substituted. The same regression command passed after the fix and the
full suite passed. The test also changes only the vector at the same ID/count and
asserts the digest changes. No diagnostic instrumentation remains in production.

`benchmark/freeze-before-reload-fix.json`, `results/selection-before-reload-fix.json`,
the original dev outputs and failed test are retained. The new freeze explicitly
records the storage correction before rerunning dev. Questions, split, model,
chunking and filter parameters were unchanged; no test metrics existed before the fix.

## Standards review

Independent Luna review found no hard documented-rule violations. It flagged two
items: repeated snapshot upsert and count-only frozen-index checking. The repeated
upsert is intentional to verify re-ingestion, and its timing explicitly includes
both writes. Count-only validation was strengthened to hash actual persisted point
IDs, payloads and vectors before test queries. Its integration tests now run and pass.

## Spec review

The earlier independent Sol review found no high-confidence implementation defects
against the reviewed requirements. That historical review did not establish runtime
correctness; the real reload defect above was subsequently found by execution.
Human labels remain an incomplete gate. No new sub-agent review was performed.

## Finish human review and submission

Read the current report and `results/test-20261115T041850787763Z/HUMAN_REVIEW.md`.
Fill actual reviewer, labels, reasons and per-hit metadata checks in the original
review forms; rerun the artifact verifier to count completed human rows. Keep test
inputs and strategy parameters frozen. Complete `docs/submission-checklist.md`.
Do not claim the required human audit or external submission has happened until it has.
