---
type: learning
status: historical
created: 2026-02-01
updated: 2026-08-13
confidence: refuted-on-main
tags: [refactoring, memory-hygiene]
---

# Stale Auto-Memory: the "Feb 2026 Simplification Pass" Never Landed on `main`

Pre-refactor agent auto-memory (the old `memory/MEMORY.md`) described a Feb 2026
simplification pass (~26 files, ~270+ lines removed) as completed. A source audit on
2026-08-13 found **most of its specifics absent from `main`**: the claimed `api/http`
helpers (`_check_status`, `_decode_json`, `_parse_pydantic`), `api/llm` extractions,
`audio/lyrics`/`audio/metadata` refactors, and `unified_map.py` `__all__` cleanup do not
exist; `curves/native.py` still uses an if/elif chain; `NullCacheSync` still wraps with
`asyncio.run` (the opposite of the claimed "direct returns").

The pass was most likely done on a branch that was never merged, or was reverted.

## Durable lessons

1. **Agent-native memory drifts from repository reality.** Never carry a claim from
   auto-memory into shared `memories/` without re-verifying it against current source —
   this is exactly why `memories/` requires provenance and `updated` dates.
2. If someone finds the unmerged simplification branch, evaluate it as a fresh change
   under `changes/` rather than trusting this historical description.

Patterns from that era that **do** verifiably exist on `main` are kept (with source
citations) in [patterns/code-patterns.md](../patterns/code-patterns.md).
