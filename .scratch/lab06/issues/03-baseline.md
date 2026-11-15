# T3: Real end-to-end baseline A

**Blocked by:** T1

**Status:** complete; actual dev/test execution and persistence verified

**What to build:** Real end-to-end baseline A as a verifiable lab deliverable.

- [x] Load/normalize/chunk with source traceability: corpus reconstruction, offsets and text-in-source checks pass.
- [x] Real model and persistent store; no fallback: model-smoke and model-artifacts record 384-D ONNX inference.
- [x] Verify re-ingestion, search and full traces: 350 A chunks, actual dev/test traces; unchanged reload and same-count vector mutation regression pass.

See docs/implementation-status.md and docs/RUN_LAB06.md for evidence and remaining gates.
