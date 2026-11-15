# T6: Metrics and human audit

**Blocked by:** T2, T5

**Status:** technical work complete; actual human review pending

**What to build:** Metrics and human audit as a verifiable lab deliverable.

- [x] Run dev and freeze selection before test: C selected on dev; no test query ran before storage bug fix/new freeze.
- [x] Save top3 and source+evidence Hit@1/Hit@3: current 60 traces/180 hit records, exact metric recomputation passes.
- [x] Compare actual resources and filter/metadata checks: resource-summary and artifact-verification available.
- [x] Prepare AI audit proposals with per-case reasons and full HUMAN_REVIEW.md packet; explicitly not human labels.
- [ ] Actual reviewer fills 30 coherence rows and 15 test rows including 45 per-hit metadata checks; current human coverage 0.

See docs/implementation-status.md and docs/RUN_LAB06.md for evidence and remaining gates.
