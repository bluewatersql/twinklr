---
type: context
area: engineering
updated: 2026-11-12
---

# Engineering Conventions

## Toolchain

Python 3.13 (3.14+ unsupported —
[constraint](../../memories/constraints/python-3.12-only.md)), uv workspace
(`twinklr-core` + `twinklr-cli`), Pydantic V2 for all data validation, Jinja2 prompt
templating, Rich CLI output.

The optional ML runtime boundary and current owner deferral are specified by the active
[P4-T1 task](../../changes/twinklr-reactivation-review/build/specs/phase-4-compounding/P4-T1-ml-chain-python-bump.md).

## Commands

```bash
make validate     # format + lint-fix + type-check + test — run before completion claims
make lint         # ruff (100-char lines)
make format       # ruff format
make type-check   # mypy (strict)
make test         # pytest
make test-cov     # pytest with coverage
make env-check    # verify uv / Python / .env setup
```

## Quality gates

All commits must pass: ruff (0 issues), mypy (0 errors), pytest (0 failures, coverage
≥ 65%). `main` is green and there are no accepted failures. The `aa8d325` failure set in
[memories/learnings/known-test-failures.md](../../memories/learnings/known-test-failures.md)
is a historical baseline, not a waiver. CI (`.github/workflows/ci.yml`) runs a format
check, lint, mypy, the tests not marked `local_only` (without coverage), and
`make version-check`.

## Style

- Strict type hints everywhere; mypy strict.
- Confirmed codebase idioms (with source citations) are collected in
  [memories/patterns/code-patterns.md](../../memories/patterns/code-patterns.md).
- Pydantic models are the single source for LLM-facing JSON schemas (auto-injection) —
  never hand-write a schema that a model already defines.

## Local configuration (gitignored — create from documented schemas)

| File | Purpose |
|---|---|
| Shell environment (`.env.example` is reference only) | API keys: `OPENAI_API_KEY` for the default cloud path; optional `GENIUS_ACCESS_TOKEN`, `ACOUSTID_API_KEY`, `HF_TOKEN`. Twinklr does not auto-load `.env`. |
| `config.json` | App settings — cache dirs, audio processing, logging |
| `job_config.json` | Job settings — agent iterations/models, fixture config path, assets, transitions, timing tracks, and final-plan checkpoint writing |
| `fixture_config.json` | Moving-head definitions — names, DMX channels, physical positions |

## Documentation conventions

Frontmatter schema and where each kind of knowledge goes:
[context/INDEX.md](../INDEX.md#metadata-convention). Change-document templates live in
`changes/_templates/`; memory and context starters in `templates/`. Both are distinct from
the product's *choreography* templates and its runtime prompt packs.

Deep reference: [docs/developer-guide.md](../../docs/developer-guide.md),
[docs/user-guide.md](../../docs/user-guide.md).
