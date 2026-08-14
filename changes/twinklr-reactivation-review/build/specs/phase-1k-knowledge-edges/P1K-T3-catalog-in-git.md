# P1K-T3 — Catalog in git (D9)

Phase: 1K · Lane: CAT · Executor: sonnet · Verifier: opus · Depends on: P1K-T1

## Objective

Establish a git-tracked home for the recipe catalog — today's ~37 hand-authored
display recipes plus a curated first mining pass over the author's local
corpus — replacing the current wholly-gitignored `data/templates/` directory, so
`TemplateStore` and `recipe_builder`'s promotion pipeline operate against
tracked project knowledge instead of an untracked directory that does not exist
in a fresh checkout. Coordinate the directory choice with P0-T2's tracked
template-fixture work so the two tasks share one data home rather than
producing two competing ones.

## Evidence & background

**D9** (`reactivation-proposal.md`, unchanged from v2): "the curated catalog is
project knowledge; raw vendor archives stay local." §2.2 item 2 ("Apply:
learned context reaches only the CLI-unreachable display planner; catalog
gitignored → CLI wiring (M3) + catalog-in-repo (D9)").

**`data/` is wholesale gitignored** (`.gitignore:52`, `# === Generated project
data & run artifacts (never check in) ===` / `data/`), and `AGENTS.md`'s
repository-hygiene section is explicit: "Never commit: ... generated artifacts
(`data/`, `artifacts/`) ...". **This means the catalog cannot simply be
un-ignored inside `data/`** — it must move to a new tracked location outside
that tree. Confirmed locally: `data/templates/` does not exist in this
checkout at all (only `data/agent_analytics`, `data/audio_cache` are present).

**All 37 shipped display-path templates are hand-authored with zero
corpus-derived markers today**, and `recipe_builder/promotion.py`'s promotion
target is this same gitignored `data/` tree — no `index.json` of
mined/promoted recipes is tracked in git anywhere (corpus-intelligence review,
"Real (indirect) production consumers exist..." section, last sentence; P6-F5
evidence list). P6-F5 (MEDIUM, gated, not blocking): "resolve source licenses
**before** resuming corpus mining or distributing mined recipes" — this task's
courtesy README must state that gate explicitly and this task's seed content
must respect it (below).

**Current file layout and consumers** (baseline `aa8d325`, re-verify before
editing):

- `sequencer/templates/group/store.py::TemplateStore.from_directory(directory)`
  reads `directory/index.json` (schema: `{"entries":[{recipe_id, name,
  template_type, visual_intent, tags, source, file}, ...]}`) and lazy-loads
  `directory/{entry.file}` (e.g. `builtins/foo.json`) as `EffectRecipe`
  (`store.py:83-160`). No format change needed — only the directory path.
- `recipe_builder/promotion.py::promote_staged_recipes(staged_dir, templates_dir)`
  copies accepted staged recipes into `templates_dir/builtins/` and appends
  entries to `templates_dir/index.json` (`promotion.py:51-120`) — the sole
  write path into the live catalog, requiring the caller to invoke it
  deliberately.
- Non-test call sites hardcoding `data/templates` today (grep-confirmed, all
  must be repointed):
  - `pipeline/display_stages.py:265-266`
  - `agents/taxonomy_utils.py:125-131` (`_get_supported_motif_ids_cached`)
  - `recipe_builder/evidence.py:63` (`DEFAULT_TEMPLATES_DIR = Path(__file__).resolve().parents[4] / "data" / "templates"`)
  - `scripts/demo_display_renderer.py:488`
  - `scripts/demo_sequencer_pipeline.py:486`
  - `scripts/demo_recipe_builder.py` (multiple references, default arg help text)
  - `scripts/enrich_builtin_templates.py` (docstring)
- Docstring-only references (update for accuracy, no behavior change):
  `sequencer/templates/group/__init__.py`, `sequencer/templates/group/store.py:3`,
  `sequencer/templates/group/enrichment.py:21` (the `.enrichment/` sidecar
  cache path).
- `EffectRecipe.provenance.source: Literal["builtin","mined","curated","generated"]`
  (`sequencer/templates/group/recipe.py:119-133`) is the existing provenance
  field — already present in the schema, just unpopulated with real
  corpus-derived values today. This task populates it correctly for seed
  content; it does not change the field.

**Coordinate with P0-T2** (`changes/twinklr-reactivation-review/build/plan/01-phase-0-foundation.md` row P0-T2):
"add a `requires_template_data` marker + fixture-presence skip for the 52
`data/templates`-dependent tests AND commit a minimal tracked template fixture
set so a representative subset runs everywhere." P0-T2's tracked fixture set
and this task's catalog home **must be the same directory** — P0-T2's minimal
fixture subset becomes the initial seed content this task expands with the
curated mining pass and full builtin set. If P0-T2 lands first at a path this
task did not anticipate, rebase this task onto it; if this task lands first,
flag the chosen path in the handoff so P0-T2's fixture-presence markers target
it. Do not create a second, separate tracked template directory.

## Current behavior

`data/templates/` (when it exists at all, e.g. after running the demo scripts
locally) is entirely untracked and gitignored. A fresh clone has no template
catalog; `TemplateStore.from_directory()` raises `FileNotFoundError` on
`index.json`, and the 52 tests P0-T2 identifies as `data/templates`-dependent
fail or must be skipped. `recipe_builder/promotion.py` writes into this same
untracked tree, so any curation work is invisible to git and lost on a fresh
checkout or a different machine.

## Target behavior

A new git-tracked directory, **`catalog/templates/`** at the repo root
(parallel to the existing top-level `context/`, `changes/`, `memories/`,
`docs/` trees), holds:

- `catalog/templates/index.json` — same schema as today's `index.json`, no
  format change.
- `catalog/templates/builtins/*.json` — the existing ~37 hand-authored recipes,
  moved verbatim (`provenance.source="builtin"`, unchanged).
- A curated first mining pass over the author's local corpus, admitted through
  `recipe_builder`'s existing staged→promoted flow
  (`provenance.source` in `{"mined","curated"}` as appropriate) — **subject to
  the licensing gate**: only recipes the author has personally confirmed are
  safe to redistribute (i.e., the composition — layer/blend/motion/parameter
  structure — not any embedded vendor sequence, audio, or media asset) are
  promoted into this tracked directory. Do not bulk-promote unreviewed
  vendor-derived mining output; this is a manual, deliberate curation pass, not
  an automated dump.
- `catalog/templates/.enrichment/` — the FE-computed sidecar cache
  (`sequencer/templates/group/enrichment.py`'s own docstring: "Recomputed by
  the FE pipeline; never needed at runtime") stays **local and regenerable**,
  not tracked — add an explicit `catalog/templates/.enrichment/` line to
  `.gitignore` even though its parent directory is now tracked.
- `catalog/templates/README.md` — the courtesy-rule document (content below).

All non-test call sites listed in Evidence are repointed from
`<repo_root>/data/templates` to `<repo_root>/catalog/templates`. Docstrings
referencing `data/templates/` are corrected to `catalog/templates/`.

**Courtesy README content** (`catalog/templates/README.md`, must cover):

- Recipes tracked here are original or cleared-for-redistribution
  *compositions* — blend modes, motion verbs, timing hints, parameter
  structures — not vendor sequence files, audio, or media assets. This
  directory never contains a copy of anyone else's `.xsq`/`.zip`/audio/image
  content.
- If you mine your own local corpus (`data/vendor_packages/`, gitignored,
  never tracked), do **not** promote or commit a recipe you have not
  personally confirmed you have the right to redistribute in this form. See
  `RecipeProvenance.source` (`builtin`/`mined`/`curated`/`generated`) for how
  each entry originated, and treat `mined`/`curated` entries as requiring that
  confirmation before promotion.
- This gate is tracked project-wide as a named, prospective risk — see
  `memories/` (or the relevant finding) for the full rationale; it is not
  blocking for work that doesn't touch mining or promotion.

**Non-goals**: no change to `index.json`'s schema, `EffectRecipe`'s schema, or
`TemplateStore`'s read logic beyond the path constant; no change to
`promote_staged_recipes()`'s logic beyond the default `templates_dir` its
callers pass; no resolution of the underlying vendor-licensing question itself
(P6-F5 remains a named, open, prospective gate — this task documents and
respects it, it does not adjudicate it); no bulk mining run as part of this
task — "a curated first pass" means a small, deliberately reviewed seed set,
not exhaustive corpus coverage (that is Phase 2K's job, per
`changes/twinklr-reactivation-review/build/plan/00-overview.md`'s program map: "M2-K ... catalog coverage").

## Implementation approach

Files/directories:

- New: `catalog/templates/` tree as described above (created via `git mv` from
  any existing local `data/templates/` content the author has, or fresh
  authoring if none exists locally — coordinate with the author/orchestrator
  on which builtin recipes currently exist to move; do not fabricate recipe
  content).
- `.gitignore` — remove any rule that would catch `catalog/` (none currently
  do — verify), add `catalog/templates/.enrichment/`.
- `packages/twinklr/core/pipeline/display_stages.py:265-266`
- `packages/twinklr/core/agents/taxonomy_utils.py:125-131`
- `packages/twinklr/core/recipe_builder/evidence.py:63` (`DEFAULT_TEMPLATES_DIR`)
- `packages/twinklr/core/sequencer/templates/group/__init__.py`,
  `store.py:3`, `enrichment.py:21` (docstrings only)
- `scripts/demo_display_renderer.py:488`
- `scripts/demo_sequencer_pipeline.py:486`
- `scripts/demo_recipe_builder.py` (default path references + help text)
- `scripts/enrich_builtin_templates.py` (docstring)
- New: `catalog/templates/README.md`

Sequencing: depends on P1K-T1 only insofar as any recipes derived from a mining
pass carry stable, content-derived provenance identifiers — if the curated
first pass uses only hand-promoted `builtin`/`curated` recipes with no
mining-derived ids embedded, T1 is not a hard blocker for the directory move
itself, but land T1 first per the plan's stated lane order regardless.
Coordinate directly with whichever agent is executing **P0-T2** — same data
home, one directory, no format divergence.

## Acceptance criteria

- `catalog/templates/index.json` and `catalog/templates/builtins/*.json` exist
  and are tracked in git — `git check-ignore catalog/templates/index.json`
  exits non-zero (not ignored).
- `catalog/templates/.enrichment/` is present in `.gitignore` and any files
  under it are not tracked.
- `TemplateStore.from_directory(repo_root / "catalog" / "templates")` loads
  successfully and returns the full recipe count (builtins + curated seed).
- Every call site listed in Evidence is repointed; `grep -rn '"data" / "templates"\|data/templates'` across
  `packages/` and `scripts/` returns zero non-historical hits (changelog/review
  documents excluded).
- `catalog/templates/README.md` exists and states the courtesy-rule content
  above.
- At least one recipe in the seed set has `provenance.source in
  {"mined","curated"}`, demonstrating the catalog is not builtins-only.
- P0-T2's fixture-presence tests (once that task lands) point at
  `catalog/templates/`, not `data/templates/` — flag this explicitly in the
  handoff regardless of landing order.

## Tests

- `tests/unit/sequencer/templates/test_store.py` (or equivalent): update/add a
  test loading `TemplateStore.from_directory()` against the real
  `catalog/templates/` tree (not a synthetic tmp fixture) and asserting a
  non-zero, expected-count recipe load.
- `tests/unit/recipe_builder/test_promotion.py`: add/verify a test that
  `promote_staged_recipes()` against a tmp copy shaped like
  `catalog/templates/` (index.json + builtins/) correctly appends new entries
  and preserves existing ones.
- A repo-hygiene check (test or CI grep step) asserting no
  `"data" / "templates"` / `data/templates` string literal remains in
  `packages/` or `scripts/` source.

## Verification commands

```bash
git check-ignore catalog/templates/index.json; echo "exit=$?"   # expect exit=1 (not ignored)
uv run pytest tests/unit/sequencer/templates/ -q
uv run pytest tests/unit/recipe_builder/test_promotion.py -q
grep -rn '"data" / "templates"\|data/templates' packages/ scripts/ || echo "clean"
uv run ruff check packages/twinklr/core/sequencer/templates packages/twinklr/core/recipe_builder
uv run mypy packages/twinklr/core/sequencer/templates packages/twinklr/core/recipe_builder
```

No LOCAL-ONLY / paid-API steps.

## Effort & risk

**M.** Mechanically simple (path rename + repoint), but the seed-content
curation step requires a human judgment call the executor cannot make alone —
the executor should scaffold the directory, README, and all repointing/tests
against a small placeholder seed set (existing hand-authored builtins is
sufficient to unblock everything else), and explicitly flag in its handoff
that the "curated first mining pass" content selection is an owner-review item
pending the author's local corpus and licensing confirmation, not something to
fabricate. Main risk: silently committing something vendor-derived — mitigated
by treating the seed set as builtins-only unless the author has explicitly
supplied and cleared mined/curated content for this task.

## Orchestrator reconciliation note (2026-08-13)

Confirmed: `catalog/templates/` is THE single tracked data home. P0-T2's test
fixtures load from it (see the matching note in P0-T2's spec) — coordinate the seed
subset so the ~52 template-dependent tests have what they assert against; test-only
pathological recipes live in `tests/fixtures/templates-extra/`, never in the catalog.
