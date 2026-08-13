---
type: pattern
status: active
created: 2026-02-01
updated: 2026-08-13
confidence: confirmed
tags: [python, style]
---

# Confirmed Code Patterns

Idioms verified against `main` on 2026-08-13 (with source citations) — prefer these when
writing or refactoring:

- **Data-driven agents** — one runner + `AgentSpec` data objects (prompt pack, response
  model, LLM settings); no agent class hierarchies.
  `packages/twinklr/core/agents/spec.py`, `async_runner.py`; see
  [multi-agent planning](../../context/architecture/multi-agent-planning.md).
- **Normalize at construction** — `_make_easing` normalizes easing objects once at
  creation; downstream code just calls `easing(t)`.
  `packages/twinklr/core/curves/functions/easing.py:53`.
- **Narrow exception handling** — `except ValueError` for Enum/validation failures, not
  `except Exception`. e.g. `packages/twinklr/core/config/fixtures/instances.py:159`.
- **Pydantic models own LLM-facing schemas** — response models generate the JSON schemas
  injected into prompts; never hand-write a schema a model already defines.

> Note: an earlier auto-memory also claimed dispatch-table conversions and sync/async
> helper extractions that are **not** on `main` — see
> [learnings/simplification-pass-2026-02.md](../learnings/simplification-pass-2026-02.md).
