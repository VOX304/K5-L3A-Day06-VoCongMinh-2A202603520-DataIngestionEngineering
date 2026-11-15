# Run the Lab06 implementation

## Current state

Real dependencies, corpus, model inference, persistent Qdrant and dev/test retrieval
are verified. `results/latest.json` points to the current completed runs; the report
uses those actual artifacts. `benchmark/questions.json` contains 20 source-checked
questions. Human audit is still pending; AI review proposals are kept separate.
See `docs/verification.md` for the fixed reload defect and preserved failed run.

## Setup (PowerShell, repository root)

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r starter/requirements-lock.txt
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe starter/scripts/prepare_corpus.py
```

The corpus is Gutenberg ebook 11, in English, paired with the English BGE-small
model. This choice avoids paid API calls and Docker. Retain `data/NOTICE.md`, the
full license and raw source alongside excerpts; see `docs/corpus-choice.md` for
the source/reuse basis.
The script downloads source only when absent. An existing copy can be supplied
with `--local-source PATH`. It rejects bytes differing from the verified source
SHA-256. The manifest records edition, source hash, acquisition-time basis and
normalized chapter-local `[start,end)` boundaries. The generated corpus contains
82 distinct units, 142,809 characters (minimum 1,500 per unit).

The lockfile records the Windows/Python 3.12 environment actually used. For another
platform, install `starter/requirements.txt`, retain the resolved versions and run
dev before test again; do not compare changed-runtime results as the original run.

The preparation script groups consecutive source paragraphs into >=1,500-character
chapter-local units, merging short tails, retaining chapter and unit IDs. At least
30 units are required. These are source units, not fabricated PDF page numbers.

Every seed quote must match the normalized source in its claimed scope. If a quote
fails, the script writes `benchmark/validation.json` and does not produce a usable
`questions.json`. Read the actual source to correct candidates, check each answer
is fully supported, and finalize the split **before** running experiments. Test
questions were drafted before any experiment; some share topics with dev, so this
small holdout does not establish generalization to unseen domains. Do not edit it
in response to test scores. Chapter filters are explicit context provided before
retrieval, not inferred from gold. All 20 current questions assume that context;
`benchmark/source_review.json` documents pre-run corrections and AI provenance.
`benchmark/freeze.json` records the current pre-run freeze; the prior freeze is
retained to document the storage-only correction before any test query ran.

## Verify and run

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
.\.venv\Scripts\python.exe -m mypy starter/src --ignore-missing-imports
.\.venv\Scripts\python.exe starter/scripts/preflight.py
.\.venv\Scripts\python.exe -m starter.src.run --split dev
.\.venv\Scripts\python.exe -m starter.src.run --split test
# Substitute the directory printed by the test command for a new reproduction:
.\.venv\Scripts\python.exe starter/scripts/verify_lab06.py --test-run test-20261115T041850787763Z
```

`python -m src.run --split dev` also works when run from `starter/`.
The first inference downloads the FastEmbed model into `starter/.cache/fastembed`.
Qdrant persists under `starter/.cache/qdrant`; keep both caches out of Git.
Dependencies/model/corpus need outbound network on first setup. Errors fail the
experiment; no mock-vector fallback is provided.

The configuration in `starter/config.json` freezes model/store/metric and A/B/C.
A uses 500-character windows with overlap 50. B groups paragraphs up to 500 chars,
hard-splitting oversized paragraphs; this is structure-aware, not semantic chunking.
C uses precisely B's chunk text and only adds supplied chapter filters. B/C document
embeddings and each query vector are reused. A/B/C indexes remain separate.

Dev selects the highest Evidence Hit@3, then Hit@1, then lowest chunk count; ties
follow A/B/C order. Test requires a matching config/corpus/benchmark/code hash from
dev selection and reuses persisted indexes. Stored IDs, payloads and vectors are
also fingerprinted so same-count index mutations are rejected. After inspecting test results, further
tuning invalidates independent holdout claims; document it and obtain fresh test
questions. Hashes catch changes, but cannot enforce honest human test handling.

The fingerprint operation reopens Qdrant from disk before reading records, ensuring
dev and test use the same stored vector representation. The regression test covers
unchanged reload and a changed vector at the same ID/count. `.gitattributes` retains
exact bytes for frozen source/code/data paths across Git checkouts.

The artifact verifier checks existing outputs without model inference or upserts.
It reproduces the corpus, recalculates metrics from all traces, checks source text
and metadata, validates model files and disk snapshots, and compares B/C payloads
and vectors. Its `--test-run` argument is an existing completed run, not a request
to rerun test. Historical failed/superseded runs remain under `results/`; current
ones are listed in `results/latest.json`.

## Read results and finish the report

Each successful run writes a timestamped directory under `results/` with metrics,
full top-3 traces, chunk statistics, dependency versions and elapsed time. Failed
backend runs write `failure.json`. Missing inputs are reported before inference.
Local inference has no API charge; electricity/hardware are not estimated.
`results/resource-summary.json` aggregates measured per-strategy timing. Dev ingest
timing includes chunking, optional embedding, two snapshot writes and fingerprint
reload. C reuses B embeddings, so its lower ingest time is not an independent
embedding speed comparison. Test's same-named timing field measures reconstruction
and verification of existing indexes, not a new ingestion.

The automatic evidence metric requires source/unit equality AND exact normalized
quote containment in one chunk. It is conservative: equivalent evidence needs a
documented alternative gold quote and review; combining fragments across chunks
does not count as the required single-chunk hit.

Fill `coherence_review.json` for the first ten sorted source units, position 0,
with 0/1/2, reason and reviewer. Test runs additionally create `test_review.json`
for every test query and strategy: inspect metadata against expected source values,
score grounding 0/1/2, and state reasons. These are deliberately blank human-audit
forms; automatic hits are not human labels. Report metadata correct/total, filter
compliance with N/A where no filter questions apply, score distributions and means.

The completed test directory also contains `HUMAN_REVIEW.md` with all sampled text,
`ai_coherence_review.json`, `ai_test_review.json` and `review_summary.json`. AI scores
are proposals from direct, unblinded source/trace reading, not human assessments.
To finish the required human audit, the actual reviewer fills each original form's
score, reason, reviewer and `status: "human-reviewed"`; every test hit also needs
`complete_and_correct` and a reason. Re-run the verifier to count completed rows.
It never copies AI scores into human forms. Current human coverage is 0/30 coherence
and 0/15 test rows (45 per-hit metadata checks).

`report/individual/2A202603520_VoCongMinh.md` now reports actual metrics, failure
examples, A–B/B–C effects and label provenance. Update its human-audit section only
after real review. Use `docs/submission-checklist.md` alongside `SUBMISSION.md`.
The repository has not been pushed/submitted by this task.

## Meaningful tests

`tests/test_pipeline.py` checks normalization, source-preserving chunking and
evidence metrics. Backend tests use tiny hand-authored vectors only as explicit
test fixtures, never as the corpus benchmark. Qdrant tests skip with a visible
reason when the dependency is absent; a skipped integration test is not proof of
working storage or retrieval. Install dependencies and rerun before submission.
