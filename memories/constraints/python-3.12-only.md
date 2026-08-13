---
type: constraint
status: active
created: 2026-08-13
updated: 2026-08-13
confidence: confirmed
tags: [environment]
---

# Python 3.12 Pinned (external ceiling now 3.13)

`requires-python` in the root `pyproject.toml` (and `twinklr-core`) pins Python 3.12;
`packages/twinklr/cli/pyproject.toml` declares a looser `>=3.10` — the workspace root
pin is the effective constraint.

**Updated 2026-08-13 (reactivation review, official-source verified):** the external
blocker has moved. Current whisperx (3.8.6) supports `>=3.10,<3.14` and pins
`torch~=2.8.0`; the whole chain now supports **Python 3.13** (3.14 remains blocked by
whisperx). Python 3.12 itself is in security-only phase. The pin is therefore a
project choice pending a coordinated bump (torch 2.4→2.8, whisperx, pyannote 3.x→4.x
major), not an external necessity — see the review's modernization assessment (M3)
and roadmap item RM-3.3. Do not bump Python as part of unrelated work; the upgrade is
its own change with full gate verification.
