# Lab06 submission readiness

This is a readiness record against `SUBMISSION.md`, not a claim that submission occurred.

- [x] 82 distinct unpaginated source units >=1,500 normalized characters; real source, boundaries, manifest and license retained.
- [x] 20 exact source-verified questions; original 15 dev / 5 test split and contextual chapter filters frozen before retrieval. AI source review is disclosed; human sign-off remains pending.
- [x] Real local 384-D model and persistent Qdrant, cosine search, metadata filtering; versions and model artifact hashes recorded.
- [x] A/B/C all executed; B/C persisted payloads and vectors equal, only filtering changes.
- [x] Current dev/test metrics, 60 full traces / 180 hit records, count/re-ingestion proof, resource measurements and zero API fee recorded.
- [x] Setup/run/verification commands, lockfile, experiment log, student info and report with two observed failure examples prepared.
- [x] Available tests pass without skips; typecheck and compilation pass. Current artifacts verified separately from historical failures.
- [x] C selected on dev before test; no tuning performed using test metrics.
- [x] Caches/venv/.env excluded from Git; no API credentials used. Source notice/license retained alongside excerpts.
- [ ] Actual reviewer completes 30 coherence rows and 15 test grounding/audit rows, including 45 per-hit metadata checks. AI proposals are not human labels.
- [ ] Update report with actual human labels/reviewer, distribution/mean and any corrections; rerun artifact verifier to count completed forms.
- [ ] Student finalizes submission commit and confirms grader repository access.
- [ ] Student submits repository link through the instructor's channel; deadline/channel were not supplied and are not guessed.

Current runs are listed in `results/latest.json`. Read
`results/test-20261115T041850787763Z/HUMAN_REVIEW.md` for the complete review packet;
edit the original `coherence_review.json` and `test_review.json` only after review.
