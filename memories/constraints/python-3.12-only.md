---
type: constraint
status: active
created: 2026-08-13
updated: 2026-08-13
confidence: confirmed
tags: [environment]
---

# Python 3.12 Only

`requires-python` in the root `pyproject.toml` (and `twinklr-core`) pins Python 3.12;
**3.13+ is not supported** (also stated in
[docs/user-guide.md](../../docs/user-guide.md)). Note `packages/twinklr/cli/pyproject.toml`
declares a looser `>=3.10` — the workspace root pin is the effective constraint. ML/audio dependencies
(WhisperX and friends) are the usual blockers. Do not bump the Python version as part of
unrelated work; treat an upgrade as its own change with full `make validate` and
`make install-dev` verification.
