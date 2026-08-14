# P2K-T1 — Coverage report tooling

Phase: 2K (M2-K) · Lane: — (standalone tooling, feeds T2/T3/T4) · Executor: sonnet ·
Verifier: sonnet · Depends on: P1K-T3 (catalog in git)

## Objective

Build a `catalog coverage` command that reads the tracked catalog (P1K-T3's home) and
a user layout file, and produces an **element-type × role(BASE/RHYTHM/ACCENT) ×
energy-range** matrix reporting, for the author's actual display, which cells have at
least one admitted recipe and which are gaps. This matrix is the phase's exit
instrument: Phase 2K (`changes/twinklr-reactivation-review/build/plan/05-phase-2k-catalog-growth.md`) is done only when
this report shows full coverage for the author's layout. Every other task in this
phase (T2's mining, T3's curation sessions) is scoped and prioritized by this
report's gap list, so its correctness and its exact axis definitions are load-bearing
for the whole phase, not just this task.

## Evidence & background

- Phase 2K exit criterion (verbatim, `changes/twinklr-reactivation-review/build/plan/05-phase-2k-catalog-growth.md:8-11`):
  "every element type in the author's layout has admitted BASE/RHYTHM/ACCENT recipe
  options across the energy range; propensity/affinity data populated per element
  type; style fingerprints exist for the author's preferred styles; catalog versioned
  in git with provenance." This task delivers the instrument for the first clause;
  T4 delivers the second and third.
- D5 / D9 (`reactivation-proposal.md:159-166,259-261`): knowledge supply is
  mining + LLM generation into one curated, git-tracked catalog; "coverage exit is
  per the AUTHOR'S layout first (design center), not universal"
  (`05-phase-2k-catalog-growth.md:26`).
- P6-F2 (REVISED) confirms the catalog's real consumer chain is
  `recipe_synthesizer.py` → `promotion.py` → `recipe_catalog.json` → `loader.py` →
  `group_planner/stage.py:30,84,292-314` (display planner context) — this coverage
  tool reports against the SAME `EffectRecipe` shape and lane vocabulary that feeds
  that consumer, not a new taxonomy.

## Current behavior (verified, baseline `aa8d325`)

- **Catalog read path**: `TemplateStore.from_directory(directory)`
  (`packages/twinklr/core/sequencer/templates/group/store.py:83-116`) loads
  `index.json` entries (`recipe_id`, `name`, `template_type`, `visual_intent`, `tags`,
  `source`, `file`) and lazy-loads full `EffectRecipe` bodies from per-file JSON on
  demand (`store.py:132-160`). `list_by_type(template_type)` already filters by lane
  (`store.py:162-163`).
- **Alternate/simpler catalog read path**: `recipe_builder/evidence.py::load_catalog()`
  loads the full flat list of `EffectRecipe` from a directory in one call, default
  `DEFAULT_TEMPLATES_DIR = Path(__file__).resolve().parents[4] / "data" / "templates"`
  (`evidence.py:63,138,148`) — i.e. `<repo-root>/data/templates` today. **This is the
  pre-P1K-T3 default and will move**: P1K-T3's spec is authoritative for the final
  tracked-catalog path; re-verify against P1K-T3's actual landed location (its own
  spec/handoff) before wiring this tool's default, and take a `--catalog-dir`
  override in the interim so the tool is not blocked on that landing order.
- **Role vocabulary**: `GroupTemplateType` has exactly five members — `BASE`,
  `RHYTHM`, `ACCENT`, `TRANSITION`, `SPECIAL`
  (`packages/twinklr/core/sequencer/vocabulary/templates.py:9-26`). The phase exit
  criterion names only BASE/RHYTHM/ACCENT — TRANSITION and SPECIAL are out of this
  matrix's scope (see Target behavior).
- **Energy vocabulary**: `EffectRecipe.style_markers.energy_affinity` is an
  `EnergyTarget` (`packages/twinklr/core/sequencer/templates/group/recipe.py:150-152`),
  five members: `LOW`, `MED`, `HIGH`, `BUILD`, `RELEASE`
  (`packages/twinklr/core/sequencer/vocabulary/energy.py:9-19`). This is the only
  energy vocabulary attached to a recipe's applicability — there is no separate
  "energy range" concept in the schema to invent; the coverage matrix's energy axis
  is these five values as-is.
- **Element-type vocabulary**: does not exist as a formal enum anywhere. The nearest
  precedent is `PropensityMiner._extract_model_type()`
  (`packages/twinklr/core/feature_engineering/propensity.py:16-36,114-121`), a
  regex-pattern table matching display-model names to 19 canonical types
  (`megatree`, `matrix`, `arch`, `candy_cane`, `snowflake`, `wreath`, `star`,
  `icicle`, `spiral`, `mini_tree`, `fence`, `roofline`, `window`, `bush`, `pillar`,
  `stake`, `spinner`, `flood`, `pixel_tree`), first-match-wins, case-insensitive,
  operating on a free-text name. `EffectRecipe.model_affinities` is
  `list[ModelAffinity]` where `ModelAffinity.model_type: str` + `score: float`
  (`recipe.py:106-116,209-212`) — the exact same free-text vocabulary, confirming
  `model_type` strings are the intended element-type identity across both the mining
  side and the recipe side. `model_affinities` defaults to `[]` and is documented as
  "empty for builtins" (`recipe.py:208-212`) — an empty list is NOT "matches nothing";
  it means the recipe was never scored against any model type (all 37 hand-authored
  builtins per P6-F5's verified count are in this state).
- **Layout read path**: `LayoutProfiler().profile(xml_path: Path) -> LayoutProfile`
  (`packages/twinklr/core/profiling/layout/profiler.py:61`) parses an xLights
  layout XML (`rgbeffects.xml`) directly — no pre-profiling step required.
  `LayoutProfile.models: tuple[ModelProfile, ...]`
  (`packages/twinklr/core/profiling/models/layout.py:160-167`); each `ModelProfile`
  has `category: ModelCategory` (`DISPLAY`/`DMX_FIXTURE`/`AUXILIARY`/`INACTIVE`,
  `packages/twinklr/core/profiling/models/enums.py:30-37`), `name`, `display_as`,
  `semantic_tags: tuple[str,...]`, `layout_group`, `pixel_count`
  (`layout.py:62-91`).
- **CLI entry-point convention**: the shipped `twinklr` console script is
  argparse-only, one subcommand (`run`) via
  `sub = p.add_subparsers(dest="cmd", required=True)` +
  `run = sub.add_parser("run", ...)` (`packages/twinklr/cli/main.py:337,339`,
  confirmed by P6-F3's verifier). There is no dispatch pattern to extend from except
  this one example.
- **Existing but layout-blind gap analysis**: `recipe_builder/evidence.py::analyze_catalog()`
  / `identify_opportunities()` (`evidence.py:197-355`) already computes
  effect-type/energy/template-type distributions and a `missing_energy_combos: list[str]`
  field (`recipe_builder/models.py:57-59`) and an `Opportunity` model
  (`models.py:70-91`) with `target_effect_type`/`target_energy`/`target_template_type`
  fields — but **no element-type/layout field exists anywhere in this path**. This
  tool is net-new coverage, not a wrapper around existing gap analysis; T3 will later
  extend `Opportunity` to carry this tool's element-type findings (P2K-T3, do not
  pre-empt that model change here).

## Target behavior

A new `catalog coverage` command (see Implementation approach for CLI wiring) that:

1. Loads the tracked catalog (all `EffectRecipe` entries, via `TemplateStore` or
   `load_catalog()` — pick whichever P1K-T3 leaves as canonical; note the choice in
   this task's own handoff since P1K-T3 lands first) and a layout XML via
   `LayoutProfiler().profile()`.
2. Derives the **element-type axis** from the layout: for each `ModelProfile` where
   `category == ModelCategory.DISPLAY`, run the same pattern-match table as
   `PropensityMiner._extract_model_type()` against `display_as` first, then `name`
   (first non-`None` match wins) — this reuses `_extract_model_type`'s regex table
   verbatim (extract it to a shared location both `propensity.py` and this tool
   import from; do not duplicate the pattern list). Models that match no pattern go
   into a distinct `unclassified` bucket — **do not silently drop them**; the report
   must show them so the author can see when the pattern table itself needs a new
   entry for their layout. Aggregate by element type (one row per distinct matched
   type present in the layout, plus `unclassified` if non-empty); record each type's
   total `pixel_count` across matched models as a prominence weight for gap ranking.
3. Derives the **role axis** as exactly `{BASE, RHYTHM, ACCENT}` — read via
   `TemplateStore.list_by_type()` per role, or filter the flat list by
   `template_type`. `TRANSITION` and `SPECIAL` are out of scope for this matrix (the
   phase exit criterion names only BASE/RHYTHM/ACCENT); do not report on them here,
   and do not silently treat them as failing coverage — they are excluded by
   design, not by omission. Say so once in the report header.
4. Derives the **energy axis** as the 5 `EnergyTarget` values, read from each
   recipe's `style_markers.energy_affinity`.
5. For each `(element_type, role, energy)` cell where `element_type` is a type
   actually present in the loaded layout (not the full 19-type pattern table —
   only what the author's layout has), computes coverage as: count of catalog
   recipes where `template_type == role` AND `style_markers.energy_affinity ==
   energy` AND (`model_affinities == []` [universal — applies to every element type]
   OR `model_affinities` contains a `ModelAffinity` entry with `model_type ==
   element_type` and `score > 0.0` [presence is the signal; do not invent a
   magnitude threshold beyond >0 — the schema attaches no documented meaning to
   sub-threshold scores today]).
6. A cell with count 0 is a gap. Rank gaps by the element type's layout prominence
   weight (pixel_count share) descending, then by role (BASE, RHYTHM, ACCENT in that
   order — foundation layers first), then by energy (LOW, MED, HIGH, BUILD, RELEASE).
7. Output: a machine-readable report (JSON) with per-cell `{element_type, role,
   energy, recipe_count, recipe_ids, is_gap}` rows, plus a summary
   `{total_cells, covered_cells, gap_cells, coverage_ratio, exit_criterion_met: bool}`
   where `exit_criterion_met` is `gap_cells == 0` over the layout-derived cell set
   (excluding `unclassified`, which is reported separately as an actionable warning,
   not folded into the pass/fail ratio). Also emit a human-readable table (stdout or
   `--out report.md`) grouped by element type, prominence-ranked, so a curation
   session (T3) can be run straight off it.
8. Non-goal: this task does not generate or curate any recipes. It does not modify
   the catalog. It is read-only tooling.

## Implementation approach

- **New module**: `packages/twinklr/core/recipe_builder/coverage.py` (or a sibling
  location if P1K-T3's spec establishes a different home for catalog-wide tooling —
  re-verify at implementation time; `recipe_builder/` is the natural fit since it
  already owns catalog-analysis code in `evidence.py`).
- **Shared regex table**: extract `_MODEL_TYPE_PATTERNS` and `_extract_model_type`
  from `feature_engineering/propensity.py:16-36,114-121` into a shared location
  (e.g. `feature_engineering/element_types.py` or `sequencer/vocabulary/`, whichever
  fits the existing module boundaries — this is a design call for the executor, not
  fixed here) and re-point `propensity.py` to import from it. Do not fork/duplicate
  the pattern list — element-type identity used for propensity mining and for
  coverage reporting must stay the single source of truth.
- **CLI wiring**: add a subcommand to the existing argparse dispatcher in
  `packages/twinklr/cli/main.py` following the established `sub.add_parser(...)`
  pattern (`cli/main.py:337,339`) — e.g. `catalog-coverage` taking `--layout <path>`
  (required), `--catalog-dir <path>` (optional, else P1K-T3's resolved default),
  `--out <path>` (optional, else stdout). **Coordinate with P1K-T4**: that task makes
  `recipe_builder` "a first-class command" in the same session — check P1K-T4's
  landed spec/PR before wiring; if it introduces a `recipe-builder`/`catalog`
  subcommand namespace, nest this command under it instead of adding a sibling
  top-level subcommand, to avoid two competing CLI conventions landing in the same
  phase.
- **Reuse, don't reimplement**: catalog loading goes through `TemplateStore` or
  `recipe_builder/evidence.py::load_catalog()` (pick one, prefer whichever P1K-T3's
  catalog format ends up matching more directly); layout loading goes through
  `LayoutProfiler().profile()` — do not hand-roll xLights XML parsing.

## Acceptance criteria

- [ ] A `catalog coverage` command exists and runs against a real layout file
  (`rgbeffects.xml`) and the tracked catalog, producing the JSON + human-readable
  report described above.
- [ ] Element-type extraction reuses the shared pattern table (single source of
  truth with `propensity.py`), not a duplicate/forked list.
- [ ] Role axis is exactly `{BASE, RHYTHM, ACCENT}`; `TRANSITION`/`SPECIAL` are
  explicitly excluded with a stated reason in the report header, not silently
  dropped.
- [ ] Energy axis is exactly the 5 `EnergyTarget` values.
- [ ] `model_affinities == []` recipes count toward every element type present in
  the layout for their (role, energy) cell; recipes with a non-empty
  `model_affinities` list count only toward listed types with `score > 0.0`.
- [ ] Models in the layout that match no element-type pattern are reported in an
  explicit `unclassified` bucket, not dropped.
- [ ] Gap ranking is prominence-weighted (pixel-count share) then role-ordered then
  energy-ordered, as specified.
- [ ] `exit_criterion_met` is computed exactly as `gap_cells == 0` over the
  layout-derived, BASE/RHYTHM/ACCENT-only cell set.
- [ ] Command is read-only: running it makes no changes to the catalog directory or
  any staged/promoted recipe files.

## Tests

- Unit test: element-type extraction against a small synthetic set of `ModelProfile`
  names/`display_as` values covering at least: an exact pattern match (`"Mega
  Tree"`), a near-miss that should land in `unclassified`, and a case-insensitive
  match.
- Unit test: coverage-cell computation with a small synthetic catalog fixture
  covering all three cases — universal recipe (`model_affinities=[]`), a
  type-restricted recipe with `score > 0`, and a type-restricted recipe with
  `score == 0` (must NOT count) or without a matching `model_type` entry (must NOT
  count).
- Unit test: gap ranking order (prominence → role → energy) on a fixture with
  multiple simultaneous gaps.
- Integration/fixture test: full command run against a small fixture layout XML +
  small fixture catalog directory, asserting the JSON report's `summary` block
  matches hand-computed expectations. Skip (not fail) if no fixture layout XML is
  committed yet — flag in the PR description that a fixture layout file needs adding
  under `tests/fixtures/` (coordinate with whatever fixture home P0-T2/P1K-T3
  establish for layout fixtures; do not invent a new one).

## Verification commands

```bash
uv run mypy packages/twinklr/core/recipe_builder/coverage.py
uv run ruff check packages/twinklr/core/recipe_builder/coverage.py packages/twinklr/cli/main.py
uv run pytest tests/unit/recipe_builder/test_coverage.py -q
uv run python -m twinklr.cli.main catalog-coverage --layout <fixture-layout.xml> --out /tmp/coverage.json  # LOCAL-ONLY (needs a real/fixture layout file)
```

## Effort & risk

**M.** Main risk: element-type extraction reusing `propensity.py`'s pattern table
may not classify every model in the author's real layout (patterns were tuned
against mined vendor sequences, not necessarily the author's own model names) —
mitigated by the explicit `unclassified` bucket rather than silent misclassification,
so the gap is visible and actionable (extend the pattern table) rather than hidden.
Secondary risk: P1K-T3's catalog location isn't fixed at spec-writing time — mitigated
by taking `--catalog-dir` as an override and treating the hardcoded default as
provisional, re-verified against P1K-T3's actual landing.
