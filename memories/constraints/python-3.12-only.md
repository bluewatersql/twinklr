---
type: constraint
status: active
created: 2026-08-13
updated: 2026-08-26
confidence: confirmed
tags: [environment]
---

# Python 3.13 Pinned (3.14 excluded)

P4-T1 coordinates the root, `twinklr-core`, and `twinklr-cli` interpreter constraint at
`>=3.13,<3.14`. Ruff, mypy, and CI target Python 3.13 as the same project-wide boundary.

**Provenance (2026-08-26, P4-T1):** the former Python 3.12-only project choice is
superseded by this coordinated bump. Python 3.13 is the only supported minor; the
optional ML runtime remains owner-deferred against the current default FFmpeg 9.
The exact compatible dependency contract, provenance, external-state closeout, and
torchaudio watch item are owned by the active
[P4-T1 task spec](../../changes/twinklr-reactivation-review/build/specs/phase-4-compounding/P4-T1-ml-chain-python-bump.md).
