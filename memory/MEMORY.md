# Twinklr Project Memory

## Project
AI-powered choreography engine for xLights (Christmas light shows).
Python 3.12+, uv, ruff (100 char), mypy strict, pytest, Pydantic V2.

## Key Commands
- `make validate` — format + lint + typecheck + test
- `uv run ruff check .` / `uv run ruff format .`
- `uv run mypy .`
- `uv run pytest tests/ -x -q`

## Package Structure (core/)
- `audio/` — 60+ files, audio analysis subdomains (rhythm, harmonic, spectral, energy, structure, lyrics, phonemes, metadata, context)
- `api/` — http client (sync+async), LLM OpenAI client, audio API (acoustid, musicbrainz)
- `caching/` — FSCache (async), NullCache, FSCacheSync, protocols
- `config/` — Pydantic models, loader, fixture config (dmx, groups, instances, physical, capabilities)
- `curves/` — DMX curve generation, 28 files, dispatch-table pattern for native curve types

## Code Patterns Confirmed
- Dispatch tables preferred over if/elif chains (curves, config)
- DRY helper extraction for sync/async duplicate code (api/http/client.py)
- Dead code removal confirmed safe for private methods in sections.py
- `NullCacheSync` uses direct returns (not asyncio.run wrappers)
- `_make_easing` normalizes easing objects at creation — downstream just calls `easing(t)`
- `except ValueError` preferred over `except Exception` for Enum validation

## Known Pre-existing Test Failures
- `tests/integration/agents/test_learning_integration.py::test_learning_context_formatting` — FAILS on main
- `tests/unit/pipeline/test_execution.py::test_execute_step_*` (3 tests) — FAIL on main
- All unrelated to audio/caching/config/curves/api packages

## Simplification Work Done (Feb 2026)
Simplified ~26 files across 5 packages (~270+ lines removed):
- `caching`: Comment cleanup, removed unused asyncio import, NullCacheSync direct returns
- `config`: Removed trivial wrappers, dict dispatch for format/channel detection, walrus ops
- `curves`: Dispatch tables for native curve types, extracted dead TypeGuard/protocols in easing
- `api/http`: Extracted _check_status, _decode_json, _parse_pydantic helpers; removed ApiErrorData; unified _merge_mappings
- `api/llm`: Extracted _track_response, _parse_json_content, _should_retry table-driven
- `audio/structure/sections.py`: Removed 3 dead private methods (~225 lines)
- `audio/lyrics/pipeline.py`: Extracted _apply_quality_penalties + _check_sufficiency
- `audio/metadata/pipeline.py`: Merged ChromaprintError + Exception handlers
- `audio/context/unified_map.py`: Removed private fns from __all__
