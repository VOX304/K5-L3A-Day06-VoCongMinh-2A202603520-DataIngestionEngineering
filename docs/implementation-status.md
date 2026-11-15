# Lab06 implementation status

Source requirements: README, GUIDE, BENCHMARK, RULES, RUBRIC, SUBMISSION.
Review base: `42f64eb230289ff5042abc03683252649dfbef79`.
Tracker: one local ticket per file in `.scratch/lab06/issues/`.

| Ticket | Status | Evidence / remaining gate |
|---|---|---|
| T1 corpus/design | Complete | Real pinned Gutenberg source; 82 units >=1,500 chars; manifest, boundaries and retained license; fixed model/store/config |
| T2 benchmark | Source verified and frozen | 20/20 exact quotes; each answer read against source with AI provenance; original 15/5 split; 20 supplied chapter filters; human sign-off pending |
| T3 baseline | Complete | Real 384-D ONNX inference and persistent Qdrant; dev/test top-3; count/idempotence and reload regression tests pass |
| T4 paragraph chunks | Complete | B runs on identical corpus/model/store; source metadata verified; observed oversized/heading limitations reported |
| T5 filter | Complete | B/C persisted payloads/vectors equal; C test filter compliance 5/5; empty-filter/persistence tests pass |
| T6 evaluate/audit | Technical work complete; human audit pending | Real dev/test metrics and 60 traces; AI proposals have individual reasons; human forms remain unfilled (0/30 coherence, 0/15 grounding/metadata rows) |
| T7 submission | Local artifacts/report complete; final submission pending | Report, run guide, student info, lockfile and checklist prepared; requires actual human audit and student's final submission |

Network/dependency/corpus blockers were resolved on 2026-11-15. There is no remaining
technical blocker. `results/latest.json` points to the verified runs:

- Dev: `results/dev-20261115T041747197624Z`; C selected by the predeclared rule.
- Test: `results/test-20261115T041850787763Z`; existing frozen indexes reused.
- `results/artifact-verification.json`: source reconstruction, metrics/traces,
  metadata, selection, model hashes, B/C equality and persisted index hashes pass.
- 20 tests pass without skips; mypy and compileall pass. See `docs/verification.md`.

The first test attempt failed at the frozen-index gate before any query because
Qdrant local returned different vector representations after restart. The bug was
reproduced and fixed by reopening from disk before exact hashing/search. The old
freeze, dev run and failed test are retained; no test score informed any change.

Human audit stays explicitly pending until actually performed. The report clearly
separates measured retrieval, automated metadata validation, and AI judgments.
Use the full [human review packet](../results/test-20261115T041850787763Z/HUMAN_REVIEW.md)
to complete original `coherence_review.json` and `test_review.json`; AI proposal files
do not satisfy that gate. No push or external submission has been performed.
