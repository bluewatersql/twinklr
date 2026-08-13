---
type: context
area: engineering
updated: 2026-08-13
---

# Engineering Conventions

## Toolchain

Python 3.12 (3.13+ unsupported —
[constraint](../../memories/constraints/python-3.12-only.md)), uv workspace
(`twinklr-core` + `twinklr-cli`), Pydantic V2 for all data validation, Jinja2 prompt
templating, Rich CLI output.

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

All commits must pass: ruff (0 issues), mypy (0 errors on new code), pytest (0 new
failures, coverage ≥ 65%). Pre-existing failures on `main` are documented in
[memories/learnings/known-test-failures.md](../../memories/learnings/known-test-failures.md).

## Style

- Strict type hints everywhere; mypy strict.
- Confirmed codebase idioms (with source citations) are collected in
  [memories/patterns/code-patterns.md](../../memories/patterns/code-patterns.md).
- Pydantic models are the single source for LLM-facing JSON schemas (auto-injection) —
  never hand-write a schema that a model already defines.

## Local configuration (gitignored — create from documented schemas)

| File | Purpose |
|---|---|
| `.env` (from `.env.example`) | API keys: `OPENAI_API_KEY` (required); optional `GENIUS_ACCESS_TOKEN`, `ACOUSTID_API_KEY`, `HF_TOKEN` |
| `config.json` | App settings — cache dirs, audio processing, logging |
| `job_config.json` | Job settings — agent iterations/model/token budget, fixture config path, checkpoints |
| `fixture_config.json` | Moving-head definitions — names, DMX channels, physical positions |

## Documentation conventions

Knowledge documents use a small YAML frontmatter schema (Obsidian-compatible, plain
Markdown otherwise). Blank starters live in `templates/` (`change.md`, `handoff.md`,
`decision.md`, `memory.md`, `context.md`) — distinct from the product's *choreography*
templates and its runtime prompt packs.

- **`type`** (primary classification): `context` · `change` · `handoff` · `decision` ·
  `learning` · `constraint` · `pattern`
- **`status`**: `active` · `accepted` · `historical` · `closed`
- **`area`** (context and change docs): `overview` · `product` · `architecture` ·
  `engineering` · `reference` — for change docs, use the domain the change touches
- **`created`** / **`updated`**: `updated` means *last substantive knowledge
  review* — don't bump it for formatting-only edits
- **`confidence`** (memories only): `confirmed` (verified against `main` with citations) ·
  `reported` (plausible, unverified provenance) · `refuted-on-main`
- Index/navigation files (`INDEX.md`, `ACTIVE.md`, `HOME.md`) carry no frontmatter.

Prefer folders + properties + links over tags; use `tags` only for cross-cutting labels
no property or link expresses.

Deep reference: [docs/developer-guide.md](../../docs/developer-guide.md),
[docs/user-guide.md](../../docs/user-guide.md).
