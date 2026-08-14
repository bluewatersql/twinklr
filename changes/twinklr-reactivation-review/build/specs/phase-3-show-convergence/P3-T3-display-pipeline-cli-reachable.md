# P3-T3 — Display pipeline CLI-reachable

Phase: 3 (Show Convergence / M3) · Lane: W (wiring) · Executor: opus · Verifier: opus
· Depends on: P1K-T3 (catalog in git), P2K-T4 (propensity/style refresh — the apply
edge's data half)

⚖ **Owner-decision-bearing.** This task adds a user-facing command and changes how
the user's display layout enters the system. The owner reviews: the command surface
(name, required inputs, defaults), the layout-source decision (rgbeffects file vs
`getModels` vs both), and the removal of the hardcoded 74-line CLI display graph.

## Objective

The display half of Twinklr — a fully built composition engine, group planner, recipe
catalog, and the repo's only from-nothing `.xsq` emitter — has never been reachable
from `twinklr`. `build_display_pipeline` exists and works; its only non-test caller is
a demo script. After this task, `twinklr` has a display/show command that builds the
choreography graph from the **user's own** xLights layout (not 74 hardcoded lines that
describe the author's display), loads recipes from the **tracked** catalog (not a
gitignored directory), and threads the feature-engineering artifact bundle into the
group planner — closing the code half of the learning loop's **apply edge**.

## Evidence & background

Findings: **Edge 2** (apply edge) from `reactivation-proposal.md` §2.2; **P7-F8 +
P7-M1** (hardcoded display graph / `fixture_count=4` / `min_pass_score=7.0` on the
shipped path); **P7-F9** (display not CLI-exposed — downgraded to INFO *under the
defer decision*, which M3 now reverses); **P5-F11** (gitignored corpus breaks 52
tests and blocks the display stage); **P6** consumer trace (FE bundle → group planner
context shaping already works when fed). Detail:
`.../reviews/phases/interfaces-and-engineering.md`,
`.../reviews/phases/display-rendering-and-xlights-io.md` §12,
`.../reviews/phases/corpus-intelligence.md` §"Real (indirect) production consumers".

### The apply edge, stated

From `reactivation-proposal.md` §2.2 (the four broken edges):

> 2. **Apply**: learned context reaches only the CLI-unreachable display planner;
>    catalog gitignored → CLI wiring (M3) + catalog-in-repo (D9).

P1K-T3 lands the catalog in git (the data half of the edge's storage); P2K-T4 lands
the propensity/style refresh "verified consumable by the display planner context (the
apply edge's data half, ahead of Phase 3's code half)". **This task is that code
half.**

### The planner context shaping already works when fed

From `.../reviews/phases/corpus-intelligence.md`:

> A repo-wide consumer trace (sub-agent survey, independently checked) found a genuine
> chain: `recipe_synthesizer.py` → `promotion.py` … → `recipe_catalog.json` →
> `loader.py::load_fe_artifacts` → `agents/sequencer/group_planner/stage.py:30,84,
> 292-314` (reads `fe_bundle.propensity_index`, `.style_fingerprint`,
> `.vocabulary_extensions` into planner prompt context) … These are **real, non-test
> call sites**, not dead code — but `group_planner` is itself part of the unreachable
> display pipeline.

Verified: `agents/sequencer/group_planner/stage.py` takes `fe_bundle:
FEArtifactBundle | None = None` in `__init__` and, in its per-section context builder
(~`:292-314`), emits `propensity_hints`, `style_constraints` (timing/transition/
layering/recipe_preferences/color_tendencies), `vocabulary_extensions`, `color_arc`,
and `color_narrative_row` into the planner variables. `feature_engineering/loader.py`
exposes `FEArtifactBundle` (frozen, `extra="forbid"`, `:26`) and
`load_fe_artifacts(fe_output_dir)` (`:71`), which reads
`feature_store_manifest.json` and defaults missing artifacts to `None`/empty.
`pipeline/definitions/display.py:44-57` already accepts `fe_bundle` as a
`build_display_pipeline` parameter. **Nothing needs to be invented here — it needs to
be called.**

### The shipped CLI is correct only for the author's own display

From `.../reviews/verification.md` §"Phase 7":

> **P7-F8 hardcoded display graph** | REVISED | MED→MED-HIGH | Merge with MISSED-1:
> "the shipped CLI is correct only for the author's own display"

> **P7-M1 (MED-HIGH, CONFIRMED)**: `cli/main.py:208` passes literal `fixture_count=4`
> into the planner prompt path (`stage.py:145` → `orchestrator.py:75`) while resolving
> the user's real fixture config three lines later — any non-4-fixture rig gets a
> planner told a false count on the only shipped path. `min_pass_score=7.0` likewise
> hardcoded (`main.py:211`).

Verified: `cli/main.py:62-135` is `build_display_graph()`, constructing a
`ChoreographyGraph(graph_id="cli_display", groups=[...])` from literal group
definitions (`fixture_count=4` at `:93`, `10` at `:108`, `1` at `:123`), plus a
hardcoded `XLightsMapping`; `:191` calls it; `:208`/`:211` pass the literal
`fixture_count=4` and `min_pass_score=7.0` into `build_moving_heads_pipeline`.
`cli/main.py:19` imports only `build_moving_heads_pipeline`.

Note the overlap with **P1P-T11**, which already retires the hardcoded rig for the
moving-heads path ("CLI: fixture config becomes the input (kills hardcoded
`fixture_count=4`, `min_pass_score`, display graph)"). By the time this task runs,
that work may have landed. **Re-verify before editing**; this task owns the display
side of the same seam and must not re-introduce or duplicate what P1P-T11 removed.

### The layout parser exists and is unwired

From `.../reviews/phases/display-rendering-and-xlights-io.md` §12:

> A real `ChoreographyGraph` source — currently 74 hardcoded lines in
> `cli/main.py:62-135` whose own comment admits layout parsing is future work. The
> layout parser exists (`formats/xlights/layout/`) and is unwired; connecting it is
> the honest fix | 2–3 days

Verified: `formats/xlights/layout/parser.py` provides `LayoutParser.parse(file_path)
-> Layout` (`:17,46`) and a `load_layout` helper (`:150`), using `defusedxml` through
the shared wrapper. Its only production consumer is `profiling/layout/profiler.py`,
itself CLI-unreachable. Known limitation to carry forward (P5-F13): "The layout parser
drops all top-level sections outside a 4-entry allow-list (`layout/parser.py:31-40,
98-100`), debug-logged only."

Second layout source, per `reactivation-proposal.md` D2 (promoted in v3) and
modernization M6b: xLights' automation API `getModels`. P2P-T12 builds the injection
workflow on that API and shares P2P-T5's client. Prefer reuse over a second client.

### The corpus blocker

From the phase doc §12, the display-wiring cost table names the real blocker:

> Restore/generate a recipe corpus — `data/templates` must exist and be non-empty or
> the stage fails at `display_stages.py:266`. Either commit a small tracked starter
> catalog or make `recipe_builder` reproducible | 2–5 days, **the real blocker**

Verified: `pipeline/display_stages.py:265-266` computes `templates_dir = _root /
"data" / "templates"` and calls `TemplateStore.from_directory(templates_dir)`, which
reads `index.json` with no existence guard (`templates/group/store.py:96-97`). `data/`
is gitignored. **P1K-T3 is this task's hard dependency for exactly this reason** — do
not work around it by regenerating a local corpus.

## Current behavior

- `twinklr run` builds a moving-heads pipeline only. `build_display_pipeline` is
  imported by no CLI code; its non-test caller is `scripts/demo_sequencer_pipeline.py`
  (which passes `enable_assets=False`).
- The choreography graph the CLI does build is 74 hardcoded lines describing one
  specific display, with a hardcoded `XLightsMapping`.
- `DisplayRenderStage` reaches for `data/templates` under the repo root — a gitignored
  path that does not exist in a clean clone.
- `FEArtifactBundle` has a loader and a consumer and no production caller connecting
  them.

## Target behavior

1. **A display/show command exists on `twinklr`.** It accepts (at minimum): the audio
   file, a layout source, an output path, and the standard config paths. Naming and
   the exact flag surface are the owner's call (⚖); propose one and implement it.
2. **Layout comes from the user.** The choreography graph and `XLightsMapping` are
   derived from the user's `xlights_rgbeffects.xml` via `formats/xlights/layout`, or
   from a live xLights `getModels` response. At least the file path must work offline;
   if `getModels` is wired, it reuses P2P-T5's client and is optional.
3. **Zero hardcoded display topology on the shipped path.** `build_display_graph()`'s
   literal groups are deleted (or demoted to an explicitly-labelled test fixture under
   `tests/`). No `fixture_count`, group id, pixel fraction, or element kind is a
   literal in `cli/`.
4. **Catalog from the tracked store.** Recipes load from P1K-T3's tracked catalog home
   (with local extensions layered on top per P1K-T3's design), not from an unguarded
   `data/templates` read. A missing catalog produces a clear, actionable error naming
   the expected path — never a bare `FileNotFoundError` from `index.json`.
5. **FE bundle threaded.** When a feature-store output directory is available, the CLI
   loads it via `load_fe_artifacts` and passes the bundle into
   `build_display_pipeline(fe_bundle=…)`, so the group planner's already-working
   context shaping receives `propensity_hints`, `style_constraints`,
   `vocabulary_extensions`, and the colour rows. When it is absent, the pipeline runs
   without it and says so once, at INFO.
6. **The demo script stops being the entry point.** `scripts/demo_sequencer_pipeline.py`
   either delegates to the new command or is deleted; it must not remain a second,
   divergent wiring of the same pipeline.
7. **Config, not literals.** `max_iterations` / `min_pass_score` / model selection come
   from the loaded job config (consistent with P1P-T11's treatment of the MH path and
   P2P-T10's config wiring), not from CLI literals.

**Non-goals**

- Do **not** change composition behavior (P3-T1/T2 own that) or the export core
  (P3-T6).
- Do **not** define the macro contract here — P3-T4 owns it; this task consumes
  whatever `MacroPlan` shape exists when it merges.
- Do **not** implement MH+display coordination — that is P3-T5.
- Do **not** enable assets. `enable_assets` stays False until P3-T7 lands its cost
  controls; wiring the flag through is fine, flipping the default is not.
- Do **not** build a general layout-editing UI or an `.xmap` generator (P1P-T11 owns
  `.xmap`).

## Implementation approach

Files expected to change:

- `packages/twinklr/cli/main.py` — new subcommand; delete `build_display_graph()`;
  remove literals.
- A new CLI-side (or `core/`-side) layout adapter: `Layout` →
  `(ChoreographyGraph, XLightsMapping)`. Put the mapping logic in `core/` so both the
  CLI and the injection workflow can use it; keep `cli/main.py` thin.
- `packages/twinklr/core/pipeline/display_stages.py` — replace the hardcoded
  `data/templates` lookup with the injected catalog/store (`recipe_catalog` /
  `template_store` are already parameters on the stage — re-verify and prefer passing
  over discovering).
- `packages/twinklr/core/pipeline/definitions/display.py` — no signature change
  expected; it already accepts `fe_bundle`, `recipe_catalog`, `choreo_graph`,
  `xlights_mapping`.
- `scripts/demo_sequencer_pipeline.py` — delegate or delete.

Design decisions already made — do not relitigate:

- Reuse `formats/xlights/layout`. Do not write a second XML parser; do not add `lxml`.
- Reuse `load_fe_artifacts` / `FEArtifactBundle`. Do not invent a parallel context
  bundle.
- Reuse `build_display_pipeline`. Do not author a new pipeline definition.
- The tracked catalog format is fixed by P1K-T3: "T3 must NOT invent a new format —
  `EffectRecipe` JSON + `index.json` as-is; only the location and tracking change."

Carry forward as a known limitation (do not fix here, do record): the layout parser's
4-entry allow-list drops unknown top-level sections with only a debug log (P5-F13). If
a real user layout loses content, file it as a finding for Phase 4's debt pass.

Sequencing constraints copied verbatim from `changes/twinklr-reactivation-review/build/plan/00-overview.md`:

> **Verification currency**: evidence in specs is from baseline `aa8d325`. Executors
> must re-verify cited line numbers before editing (the tree will drift as phases
> land) — specs cite symbol + file, with line numbers as hints only.

> `make validate` equivalents (check-only forms until P0-T4 lands the guard) must pass
> at every merge; golden tests (once P1P-T1 exists) must pass for any lane touching
> render/export code.

> ⚖-marked tasks (owner-decision-bearing) say so at the top and name what the owner
> reviews.

> Nothing in this program authorizes pushes/PRs to remotes or paid API calls beyond
> each spec's stated test budget; live-LLM and xLights-GUI tests are marked
> `LOCAL-ONLY` in specs and excluded from CI.

From `changes/twinklr-reactivation-review/build/plan/06-phase-3-show-convergence.md`: Lane W is `T3 → T4 → T5`. This task
is first in the lane; T4 and T5 rebase on it. `cli/main.py` is also touched by
**P1P-T11** (different phase, earlier merge) — rebase, do not revert its changes.

## Acceptance criteria

1. `twinklr <display-command> --help` lists the command; running it against a sample
   layout + audio produces a `.xsq` (or the configured delivery artifact) without any
   code change or environment variable beyond the documented ones.
2. Given two different `xlights_rgbeffects.xml` files, the produced choreography graph
   differs and reflects each file's models/groups — proving the layout is read, not
   assumed.
3. `grep -rn "cli_display\|fixture_count=4\|min_pass_score=7.0" packages/twinklr/cli/`
   returns nothing.
4. The group planner's prompt variables for a run with an FE bundle contain
   `propensity_hints`, `style_constraints`, and `vocabulary_extensions`; the same run
   without a bundle contains none of them and logs one INFO line. (Assert on the
   built variables, not on a live LLM call.)
5. A run with the tracked catalog present succeeds from a **clean clone** with no
   `data/` directory. A run with the catalog absent fails with a message naming the
   expected catalog path.
6. `grep -rn "build_display_pipeline" packages/ scripts/` shows the CLI (and tests) as
   callers; `scripts/demo_sequencer_pipeline.py` either delegates or is gone.
7. `enable_assets` remains False on every shipped path (grep-verified).
8. The moving-heads command's behavior and golden outputs are unchanged.

Golden-diff expectations: this task changes no render math. MH goldens must be
byte-identical. The new display path gets its **first** golden artifact — commit the
generated `.xsq` (or its normalized text form) for the sample layout + a deterministic
plan fixture, so P3-T5/T6 have a BEFORE to diff against. The review notes the repo has
never contained a sample `.xsq`; this is the place that changes.

## Tests

New, all clean-clone-safe:

1. `tests/unit/cli/test_display_command.py::test_command_registered_and_args` —
   parser-level, no execution.
2. `tests/unit/sequencer/display/test_layout_to_choreo_graph.py` — a small tracked
   `xlights_rgbeffects.xml` fixture → `ChoreographyGraph` + `XLightsMapping`; assert
   group ids, element kinds, and mapping entries. Add a second fixture with a
   different topology and assert the graph differs.
3. `tests/unit/pipeline/test_display_pipeline_wiring.py::test_fe_bundle_threaded` —
   build the pipeline with a synthetic `FEArtifactBundle`; assert the group-planner
   stage's per-section context contains the three keys. And
   `…::test_runs_without_fe_bundle`.
4. `tests/unit/pipeline/test_display_stage_catalog_source.py` — the stage reads the
   injected catalog; a missing catalog raises a message containing the path.
5. `tests/integration/test_display_pipeline_e2e.py` — end-to-end with a fake LLM
   provider (the repo has 57 mock sites; prefer whatever centralized fake exists by
   then — P7-F15) and a deterministic plan fixture, asserting a `.xsq` is written and
   matches the committed golden.

Mark the integration test `@pytest.mark.integration` — P7-F7 records that 14 of 16
integration files are unmarked and `pytest -m integration` selects only 2; do not add
to that.

## Verification commands

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy .

uv run pytest tests/unit/cli/ tests/unit/pipeline/ tests/unit/sequencer/display/ -v
uv run pytest tests/integration/test_display_pipeline_e2e.py -v

uv run pytest tests/ -q      # no NEW failures vs the verification.md baseline
uv run pytest tests/golden -v

# clean-clone proof (run from a fresh worktree with no data/ directory)
uv run twinklr <display-command> --help
```

LOCAL-ONLY:

- Any `getModels` path requires a **running windowed xLights** and is excluded from
  CI. Mark it `LOCAL-ONLY` and skip by default.
- A real end-to-end run with live LLM calls is LOCAL-ONLY. **Test budget: one live
  end-to-end display run, at the job config's default models, for the owner's
  acceptance demo only — CI and automated verification must use the fake provider and
  spend $0.**

## Effort & risk

**Size: L** (the phase review costed the CLI subcommand at ~1 day and the real
`ChoreographyGraph` source at 2–3 days).

**Main risk: the corpus dependency.** The review is blunt that the catalog is "the
real blocker … a *data* problem, not a code problem". If P1K-T3's tracked catalog is
thin or absent at merge time, this task produces a command that runs and renders
nothing useful. *Mitigation*: the acceptance criteria require a clean-clone run
against the tracked catalog; if that catalog cannot support a real render, stop and
report rather than regenerating a local corpus to make the test pass.

**Secondary risk: layout-mapping fidelity.** Mapping a real xLights layout onto
`ChoreographyGraph`'s role/prominence/position vocabulary is judgement work, and the
parser silently drops unknown sections (P5-F13). *Mitigation*: two contrasting layout
fixtures in tests, and a run-time summary line listing the groups derived from the
layout so a user can see what was understood.
