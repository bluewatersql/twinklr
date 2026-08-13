---
type: learning
status: active
created: 2026-02-01
updated: 2026-02-01
confidence: reported
tags: [testing]
---

# Known Pre-existing Test Failures on `main` (reported Feb 2026)

Pre-refactor agent memory reported four tests failing on `main` independent of any
in-flight work:

- `tests/integration/agents/test_learning_integration.py::test_learning_context_formatting`
- `tests/unit/pipeline/test_execution.py::test_execute_step_*` (3 tests)

**Provenance caveat:** this comes from the same auto-memory source that contained stale
claims (see [simplification-pass-2026-02.md](simplification-pass-2026-02.md)). Before
relying on it, re-verify with a fresh `make test` run; then update `updated` here —
or delete this memory if the failures are gone or fixed.

Until re-verified: do not treat these four as regressions caused by your change, and do
not claim the suite is fully green.
