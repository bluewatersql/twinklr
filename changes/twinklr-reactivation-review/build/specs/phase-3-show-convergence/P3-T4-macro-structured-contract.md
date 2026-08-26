# P3-T4 — Macro structured contract (D3)

Phase: 3 (Show Convergence / M3) · Lane: W (wiring) · Executor: opus · Verifier: opus
· Depends on: P2P-T1 (plan schema v2), P3-T3

⚖ **Owner-decision-bearing.** This task defines the cross-element coordination
vocabulary the whole product's "part 2" rests on. The owner reviews: the field list
below (what a macro plan is allowed to say), the deletions from today's `MacroPlan`,
and the precedence rule between macro-level and section-level choices.

> **This spec is the single definition of the macro contract for the whole program.**
> `changes/twinklr-reactivation-review/build/plan/06-phase-3-show-convergence.md` states it directly: "T4 is
> design-bearing and shared with 2P's schema work — the spec defines the contract
> ONCE; MH and display specs reference it." Any other spec that needs macro fields —
> the MH schema-v2 work (P2P-T1/T2), P3-T5's coordination, P3-T8's evaluation rubric —
> **references this document** and does not restate or extend the contract locally. A
> change to the contract is a change to this spec.

## Objective

The macro planner is the product's cross-element coordination spine — "arches answer
the megatree" is a macro statement — and today its entire output reaches the shipped
renderer as **prompt prose**. After this task, `MacroPlan` is a slim, typed contract
whose fields are consumed programmatically by both back-ends: the display planner
(first consumer, live in this phase) and moving-head schema-v2 (second consumer).
Fields nothing consumes are deleted rather than left as solicited-and-dropped LLM
work.

## Evidence & background

Findings: **P3-F1** (CRITICAL, CONFIRMED — `MacroPlan` reaches the shipped renderer
only as prompt prose), **P3-F12** (20 dead solicited fields, corrected from 33 at
verification), **CF-3** (the strategic finding: "LLM→renderer channel is two strings
wide"), decision **D3** in `reactivation-proposal.md`. Detail:
`.../reviews/phases/llm-agents-and-planning.md` §10;
`.../reviews/verification.md` §"Phase 3".

### P3-F1, quoted

> **P3-F1 — `MacroPlan` reaches the shipped renderer only as prompt prose**
> `CRITICAL` · `CONFIRMED` · IMPLEMENTATION_DIVERGES_FROM_INTENT · **SIMPLIFY**
>
> Grep-verified: zero occurrences of `MacroPlan` or `macro_plan` anywhere under
> `packages/twinklr/core/sequencer/moving_heads/`. The only route is
> `MovingHeadPlanningContext.macro_plan` → `for_prompt()` builds a list of dicts
> (`agents/.../moving_heads/context.py:208-228,243`) → `build_planner_variables`
> (`orchestrator.py:88`) → `planner/user.j2:129` and `judge/user.j2:51-59`. No import,
> no state key, no threading. **Refinement — one indirect route does exist and Stage 2
> did not name it:** `MovingHeadPlannerOrchestrator.get_cache_key` includes the full
> serialized macro plan (`orchestrator.py:236-238`), so `MacroPlan` content
> participates in the MH stage's cache identity. It changes *whether* a cached plan is
> reused, never *what* is rendered. This strengthens rather than weakens the claim: the
> macro planner's only non-prose effect on the shipped path is cache invalidation.

Verified: `agents/sequencer/moving_heads/context.py:208-228` builds `macro_guidance`
as a list of dicts (`section_id`, `energy_target`, `motion_density`,
`choreography_style`, `palette_id`, `motif_ids`, `notes`) and `:243` places it under
the `"macro_plan"` prompt key. That seven-key dict is, today, the *entire* macro→MH
channel — and it is a prompt string, not a typed input.

One typed consumer **does** exist and must not be broken:
`pipeline/display_stages.py:331-345` reads `context.state["macro_plan"]`, validates it
to `MacroPlan`, and derives section boundaries from `macro_plan.section_plans`
(`:345`). That is the one place macro output is already used as data.

### D3, quoted

From `reactivation-proposal.md` §3:

> **D3 — Macro planner** *(unchanged)*: repair to a structured contract; it is the
> cross-element coordination spine ("arches answer the megatree" is a macro
> statement).

### CF-3 and the dead-field discipline

From `reviews/findings.md`:

> | CF-3 | LLM→renderer channel is two strings wide; macro plan reaches renderer only
> as prompt prose; 20 dead solicited fields; categorical vocabulary never imported by
> renderer (refutes docs + decision record) | HIGH (strategic) | P3-F1/F12,
> P4-F17/F18/F23 | PROJECT DECISION → RM-2.* |

From `verification.md` §"Phase 3":

> **F12: 20 dead solicited fields, not 33** … (9 have real readers incl.
> `MacroPlan.asset_requirements` — which F17 itself cites; contradiction resolved in
> F12's favor of deletion). Cause: sweep missed whole-model `model_dump()` prompt
> dumps.

The lesson to apply: a field is "consumed" only if code reads it by name. Appearing
inside a whole-model `model_dump()` that is rendered into a prompt is **prose**, not
consumption.

### Today's model (verified, `sequencer/planning/models.py`)

- `MacroPlan` (`:273`): `global_story: GlobalStory`, `layering_plan: LayeringPlan`,
  `section_plans: list[MacroSectionPlan]` (min 1), `asset_requirements: list[str]`
  (max 50).
- `MacroSectionPlan` (`:113`): `section: SongSectionRef`, `theme: ThemeRef`,
  `energy_target: EnergyTarget`, `primary_focus_targets: list[PlanTarget]` (1–8),
  `secondary_targets: list[PlanTarget]` (≤12), `choreography_style:
  ChoreographyStyle`, `palette: PaletteRef | None`, `motif_ids: list[str]` (≤5),
  `motion_density: MotionDensity`, `notes: str` (min 20 chars).
- `LayeringPlan` (`:234`) / `LayerSpec` (`:210`): `layer_index` 0–4, `layer_role`,
  `target_selector` (roles + a free-text `coordination` string, default `"unified"`),
  `blend_mode`, `timing_driver`, `intensity_bias`, `usage_notes` (min 10 chars).
- `model_config = {"extra": "forbid"}` on all of these.

Existing vocabulary to reuse (do not invent parallel enums):
`sequencer/vocabulary/energy.py` — `EnergyTarget` (LOW/MED/HIGH/BUILD/RELEASE/PEAK),
`MotionDensity` (SPARSE/MED/BUSY), `ChoreographyStyle` (IMAGERY/ABSTRACT/HYBRID);
`sequencer/vocabulary/coordination.py` — `CoordinationMode` (UNIFIED / COMPLEMENTARY /
SEQUENCED / CALL_RESPONSE / RIPPLE), `StepUnit`, `SpatialIntent`;
`sequencer/vocabulary/composition.py` — `LayerRole`, `BlendMode`;
`sequencer/templates/group/models/coordination.py:30` — `PlanTarget`;
`sequencer/theming/models.py:113` — `ThemeRef`; `sequencer/planning/models.py:22` —
`PaletteRef`; `agents/audio/profile/models.py:87` — `SongSectionRef`.

Structured-outputs constraint inherited from P2P-T1/T11: "schema stays
strict-structured-outputs-compatible (all-required, no top-level unions)". The macro
schema must satisfy the same rule.

## Current behavior

- The macro planner produces a rich `MacroPlan`; the MH planner receives seven of its
  fields flattened into a prompt string; the display path reads only
  `section_plans[*].section` for boundaries.
- `layering_plan` reaches nothing programmatically. `global_story`,
  `choreography_style`, `motif_ids`, `theme`, `palette`, `primary_focus_targets`, and
  `secondary_targets` reach nothing programmatically on the MH path.
- `asset_requirements` is validated by `macro_planner/heuristics.py:324,492` and is
  otherwise dead as an output (it does not drive asset generation; the asset path
  reads `GroupPlanSet.narrative_assets`).
- Cross-element coordination — the thing the macro planner exists for — has **no typed
  representation at all**. `TargetSelector.coordination` is a free-text string with a
  `"unified"` default.

## Target behavior — THE CONTRACT

`MacroPlan` becomes the following (names are normative; types reuse existing
vocabulary; every field is `extra="forbid"` and required unless marked optional).

### Song level

| Field | Type | Meaning | First consumer |
|---|---|---|---|
| `sections` | `list[MacroSection]`, min 1 | Per-section contract, below | display planner + section boundary derivation |
| `palette_arc` | `list[PaletteStop]`, min 1 | Ordered palette/theme progression across the song | display planner (section palettes), MH schema-v2 (colour intent) |
| `motif_continuity` | `list[MotifThread]` | Which motifs recur, where, and how they evolve | display planner (recipe/motif selection), assets (P3-T7) |
| `focal_arc` | `list[FocalAssignment]` | Which element role carries the show at each section | both back-ends |

### `MacroSection` (per song section)

| Field | Type | Meaning | Notes |
|---|---|---|---|
| `section` | `SongSectionRef` | id / name / start_ms / end_ms | unchanged; already the boundary source |
| `energy_target` | `EnergyTarget` | LOW…PEAK | unchanged enum |
| `motion_density` | `MotionDensity` | SPARSE/MED/BUSY | unchanged enum |
| `choreography_style` | `ChoreographyStyle` | IMAGERY/ABSTRACT/HYBRID | unchanged enum |
| `palette_role` | `PaletteRoleRef` | which `palette_arc` stop applies, plus optional per-section override | replaces the loose `palette: PaletteRef \| None` |
| `theme` | `ThemeRef` (SECTION-scoped) | unchanged validator | keep |
| `motif_ids` | `list[str]`, ≤5 | motifs emphasised here; must resolve into `motif_continuity` | validated cross-reference (new) |
| `focal_roles` | `list[FocalRole]`, min 1 | which element roles lead / support / rest | **new, typed** |
| `call_response_pairs` | `list[CallResponsePair]` | explicit "X calls, Y answers" statements | **new, typed** |
| `coordination_intent` | `CoordinationMode` | the section's dominant cross-element relationship | **new**, reuses the existing enum |
| `notes` | `str`, min 20 | prose the planner prompt may still use | retained *as prose, labelled as such* |

### New typed sub-models

- **`PaletteStop`**: `stop_id: str`, `palette: PaletteRef`, `applies_from_section_id:
  str`, `transition: PaletteTransition` (enum: `HOLD` / `CROSSFADE` / `CUT`).
- **`PaletteRoleRef`**: `stop_id: str`, `override: PaletteRef | None`.
- **`MotifThread`**: `motif_id: str`, `section_ids: list[str]` (min 1),
  `evolution: MotifEvolution` (enum: `INTRODUCE` / `RESTATE` / `VARY` / `RESOLVE`),
  `description: str`.
- **`FocalRole`**: `target: PlanTarget`, `role: FocalRoleKind` (enum: `LEAD` /
  `SUPPORT` / `REST`).
- **`FocalAssignment`**: `section_id: str`, `lead_target: PlanTarget`.
- **`CallResponsePair`**: `call: PlanTarget`, `response: PlanTarget`,
  `step_unit: StepUnit`, `step_duration: int` (≥1).

### Deletions

- `layering_plan` / `LayeringPlan` / `LayerSpec` / `TargetSelector` — **delete** unless
  the executor's own grep finds a by-name production reader. (At baseline there is
  none; `layer_index`/`blend_mode`/`timing_driver` reach output through no code path.)
  If a reader is found, keep the minimum subset and record the finding.
- `global_story` — keep **only** the members with a named consumer after this task
  (the theme/motif registry references); fold the rest into `motif_continuity` and
  `palette_arc`. Prose-only members go to `notes`.
- `asset_requirements` — delete from `MacroPlan`. Assets are driven by
  `GroupPlanSet.narrative_assets` (P3-T7); keeping a second, unread requirement list
  reproduces exactly the F12 defect. Update `macro_planner/heuristics.py:324,492`
  accordingly.
- `primary_focus_targets` / `secondary_targets` — replaced by `focal_roles`
  (LEAD/SUPPORT/REST expresses the same intent with a consumer).

### Behavioral requirements

1. **Every field above has a by-name reader in production code by the end of Phase 3.**
   `focal_roles`, `call_response_pairs`, `coordination_intent`, `palette_role`, and
   `motif_continuity` are consumed by the display planner/composition path (P3-T5 wires
   the coordination half). Any field that ends the phase without a named reader is a
   spec violation, not an acceptable leftover.
2. **Typed input, not prose.** The macro contract enters section planning as model
   objects on the pipeline context/state, not (only) as prompt variables. Prompts may
   *additionally* render them; the rendering must be derived from the typed object,
   never the sole channel.
3. **`notes` is explicitly prose.** It is the one field allowed to have no structured
   consumer, and its docstring says so.
4. **Cross-reference validation.** `motif_ids` must resolve to a `MotifThread`;
   `palette_role.stop_id` must resolve to a `PaletteStop`; `call_response_pairs` and
   `focal_roles` targets must resolve against the choreography graph's groups when one
   is available. Validation failures are loud.
5. **Structured-outputs compatible.** All-required fields, no top-level unions, so
   P2P-T11's `json_schema` migration applies unchanged.
6. **Precedence stated.** Where a section-level value could conflict with a song-level
   one (`palette_role.override` vs `palette_arc`), the rule is written down in the
   model docstring and in the decision record.

**Non-goals**

- Do **not** implement the MH schema-v2 consumption here — P2P-T1/T2 own that; this
  task delivers the contract they consume. If P2P-T1 has already landed, reconcile
  (see "Implementation approach") rather than fork.
- Do **not** implement the display-side coordination behaviour — P3-T5 owns it.
- Do **not** change the macro judge, iteration, or cache-key behavior (P2P-T9 / P1P-T9
  own those). But **do** note that `get_cache_key` serializes the whole macro plan
  (`orchestrator.py:236-238`) — changing the model changes cache identity, which is a
  clean miss, not a correctness problem.
- Do **not** add asset fields back under a new name.

## Implementation approach

Files expected to change:

- `packages/twinklr/core/sequencer/planning/models.py` — the contract itself.
- `packages/twinklr/core/agents/sequencer/macro_planner/{specs,heuristics,context,
  orchestrator,stage}.py` — schema injection, heuristic validators, prompt variables.
- `packages/twinklr/core/agents/sequencer/macro_planner/prompts/**` — prompt templates
  reflecting the new schema (schema auto-injection is a verified strength, ST-1:
  "Schema/taxonomy auto-injection — zero drift by construction" — use it; do not
  hand-maintain a second copy of the schema in prose).
- `packages/twinklr/core/agents/sequencer/moving_heads/context.py` — the seven-key
  `macro_guidance` dict becomes a derivation of the typed object.
- `packages/twinklr/core/pipeline/display_stages.py` — boundary derivation follows the
  renamed field (`sections` vs `section_plans`).
- `packages/twinklr/core/agents/sequencer/group_planner/**` — accept the typed macro
  contract as a section-planning input.

Design decisions already made — do not relitigate:

- The contract is **slimmed**, not extended in place. D3 says "repair to a structured
  contract"; F12's lesson is that unread fields are a defect class, not neutral.
- Reuse existing vocabulary enums. The review's V-categorical verdict for moving heads
  ("zero vocabulary imports under moving_heads/…") is a defect to fix, not a pattern to
  copy — new parallel enums would repeat it.
- The display planner is the **first** consumer; MH schema-v2 is the second. Design
  the fields against display's needs and verify MH can consume them, not the reverse.

**Reconciliation with P2P-T1.** P2P-T1 (plan schema v2) lands first and touches
`agents/shared` + schemas; `changes/twinklr-reactivation-review/build/plan/04-phase-2p-creative-quality.md` notes "T1 and
T9 both touch `agents/shared`+schemas: T1 lands first; T9 rebases." The same applies
here: rebase on P2P-T1's schema work. If P2P-T1 introduced a macro-adjacent field that
duplicates one above, **this spec's name and shape win** and P2P-T1's is renamed to
reference it — that is the point of defining the contract once.

Deliverable beyond code: a decision record in `memories/decisions/` capturing the
contract, the deletions and why, and the precedence rule. Per `AGENTS.md`, that is
where durable decisions live; a docstring is not sufficient for a contract other specs
reference.

Sequencing constraints copied verbatim from `changes/twinklr-reactivation-review/build/plan/00-overview.md`:

> **Verification currency**: evidence in specs is from baseline `aa8d325`. Executors
> must re-verify cited line numbers before editing (the tree will drift as phases
> land) — specs cite symbol + file, with line numbers as hints only.

> Cross-lane file conflicts are called out in the task tables; when unavoidable, the
> later lane rebases.

> ⚖-marked tasks (owner-decision-bearing) say so at the top and name what the owner
> reviews.

> Nothing in this program authorizes pushes/PRs to remotes or paid API calls beyond
> each spec's stated test budget; live-LLM and xLights-GUI tests are marked
> `LOCAL-ONLY` in specs and excluded from CI.

From `changes/twinklr-reactivation-review/build/plan/06-phase-3-show-convergence.md`: Lane W is `T3 → T4 → T5`.

## Acceptance criteria

1. `MacroPlan` matches the contract above field-for-field (names, types, cardinalities,
   optionality). Deviations are documented in the decision record with rationale.
2. **Zero unread fields.** A test (or a checked-in script) enumerates `MacroPlan`'s
   leaf fields and asserts each one is referenced by name in non-test production code,
   with `notes` as the single declared exception. This test is the mechanical guard
   against re-creating F12.
3. `grep -rn "layering_plan\|asset_requirements\|primary_focus_targets" packages/`
   returns only historical/changed-doc hits — no live model or reader.
4. The typed macro object reaches section planning as an object: a test asserts the
   group-planner stage receives `MacroPlan`-typed input (or a typed projection of it),
   not a dict-of-strings.
5. `agents/sequencer/moving_heads/context.py`'s macro prompt block is generated from
   the typed contract (assert the derivation, so a field rename cannot silently empty
   the prompt — the F5 failure mode).
6. Cross-reference validation fires: a plan whose `motif_ids` names an absent
   `MotifThread`, or whose `palette_role.stop_id` is unknown, is rejected with a
   message naming the offending value.
7. The schema is strict-structured-outputs compatible: a test asserts all-required
   fields and no top-level unions (reuse whatever check P2P-T11 introduces; if it has
   not landed, write the assertion here).
8. `pipeline/display_stages.py`'s section-boundary derivation still works and its tests
   pass.

Golden-diff expectations: no render math changes; MH and display goldens byte-identical
**except** where a golden's plan fixture encodes the old macro shape — those fixtures
are regenerated, and the regeneration is called out explicitly in the PR body with a
before/after of the fixture, not folded into an unexplained golden update.

## Tests

TDD — failing first.

1. `tests/unit/sequencer/planning/test_macro_contract.py::test_contract_fields` — the
   normative field list, as an executable spec.
2. `…::test_every_field_has_a_named_reader` — acceptance criterion #2. This is the
   most important test in the task.
3. `…::test_motif_cross_reference_validation` and
   `…::test_palette_stop_cross_reference_validation`.
4. `…::test_focal_and_call_response_targets_resolve_against_graph`.
5. `…::test_schema_is_structured_outputs_compatible`.
6. `tests/unit/agents/sequencer/moving_heads/test_macro_prompt_derivation.py` — the MH
   prompt block is derived from the typed object; a renamed field breaks the test
   rather than silently emptying the prompt.
7. `tests/unit/pipeline/test_display_stage_boundaries.py` — regression: section
   boundaries still derive correctly from the renamed field.
8. `tests/unit/agents/sequencer/group_planner/test_typed_macro_input.py` — the planner
   stage receives the typed contract.

Existing macro-planner tests (heuristics, orchestrator, stage) must be updated
deliberately; any test asserting a deleted field is removed **with** a one-line note in
the PR body saying which field and why.

## Verification commands

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy .

uv run pytest tests/unit/sequencer/planning/ -v
uv run pytest tests/unit/agents/sequencer/macro_planner/ -v
uv run pytest tests/unit/agents/sequencer/moving_heads/ -v
uv run pytest tests/unit/agents/sequencer/group_planner/ -v
uv run pytest tests/unit/pipeline/ -v

uv run pytest tests/ -q      # no NEW failures vs the verification.md baseline
uv run pytest tests/golden -v
```

## Implementation handoff — 2026-08-16

Status at author freeze (historical): **exact contract/invariants and AC2 amendment owner-accepted; live attempt 1
safely rejected by the provider schema validator; general offline schema remediation
frozen pending fresh independent verification; live acceptance open and not integrated.** Author worktree:
`/tmp/twinklr-p3t4.next`, based on
`33cce57`. The author did not perform the owner live call and has not performed xLights,
audio, commit, or integration action. The canonical owner-local ledger/evidence remains
outside this repository and was not modified during remediation.

### Red-first evidence

The first executable contract test failed during collection because
`CallResponsePair` and the new contract did not exist. Expanding the focused surface
then produced 57 failures and 28 errors across 448 tests, discriminating the legacy
list-shaped state, stale group contexts, flattened moving-head input, and prompt
vocabulary. After migration, the focused contract/macro/group/MH/display surface is
455 passed. The first broad-suite run then exposed 13 failures and 10 errors in stale
integration, cache, prompt-matrix, taxonomy, and recipe fixtures; the exact affected
subset passed 43 tests after deliberate migration, and the complete suite then passed.

### Implemented contract and seams

- Replaced the legacy macro/story/layer/focus models with the exact four-field
  `MacroPlan` and typed sub-models; added intrinsic cross-reference, ordering, focal,
  palette/theme, call/response, and optional choreography-graph validation.
- Added external audio/catalog/layout heuristics and wired the actual palette and motif
  catalogs into validation.
- Retained the full typed plan in pipeline state, used only `sections` for fan-out, and
  atomically canonicalized section IDs plus palette, motif, and focal references.
- Added a lossless typed group projection and made group prompt/cache identity consume
  it. Unknown typed targets fail loudly.
- Changed moving-head planning to retain the full typed plan; song-level palette,
  motif, and focal edits affect both prompt derivation and cache identity.
- Changed holistic summary/prompt/cache handling to preserve the full typed contract.
- Replaced legacy macro planner/judge prompts and removed live legacy field readers.
  Existing display/MH output behavior and goldens are intentionally unchanged.

### Owner decisions and explicit boundary

The exact shape and invariants are recorded in
[`typed-macro-coordination-contract.md`](../../../../../memories/decisions/typed-macro-coordination-contract.md)
with `status: accepted`. On 2026-08-16 the owner accepted the exact four-field contract,
its recorded invariants, and the AC2 amendment: P3-T4 must prove recursive
mutation-discriminating typed/by-name projection, prompt, cache, and validation readers;
P3-T5 remains the first emitted-display behavioral consumer of `call_response_pairs` and
`coordination_intent`. No fake sink or expected-fail test was added. The owner authorized
only P3-T4's capped live macro probe (at most three attempts, additionally constrained
by one cumulative `$1.75` task budget). Attempt 1 ran after harness-audit GO and failed
safely as recorded below; live acceptance remains open.

### Superseded verification snapshot

The counts below preceded formal verifier rejection and are historical only. They are
not current acceptance evidence; the remediated snapshot must record fresh gates.

- focused contract/macro/group/MH/display: `455 passed in 1.43s`
- repository formatting/lint: `1343 files already formatted`; Ruff `All checks passed!`
- mypy: `Success: no issues found in 721 source files`
- immutable goldens: `73 passed, 8 skipped in 2.06s`; no regeneration or byte change
- full offline suite without coverage: `5229 passed, 39 skipped in 79.27s`
- canonical coverage-enabled suite: `5229 passed, 39 skipped in 96.77s`, 87% total
  coverage
- `git diff --check`: clean

`make validate` itself was not runnable in the author worktree because its first guard
requires no uncommitted changes, while the executor was explicitly forbidden to commit
or stash. It exited before executing a gate. Its four component commands were therefore
run directly and all passed as recorded above. Installing the optional Anthropic extra
temporarily made mypy report four errors in the unchanged base provider's optional
import fallback; removing that optional environment-only package restored the canonical
clean 721-file result without a source change.

### Formal-rejection remediation snapshot

The verifier's executable defects were reproduced before remediation: the initial
adversarial subset produced `6 failed, 3 passed`, then passed `9/9` after exact audio
section equality, bidirectional motif membership, theme/tag catalog checks, deterministic
group metadata stamping, empty-motif support, corrector preservation, and target
semantics were fixed. Replacing the whole-model AC2 assertion with the recursive named
leaf registry first produced `2 failed`; the mutation-discriminating readers then passed
`2/2` and are used by group, moving-head, and holistic prompt/cache derivation.

Fresh frozen author gates:

- focused contract/macro/group/MH/display: `494 passed in 1.85s`
- repository formatting/lint: `1343 files already formatted`; Ruff `All checks passed!`
- mypy: `Success: no issues found in 720 source files`
- immutable goldens: `73 passed, 8 skipped in 2.09s`; no regeneration or byte change
- full coverage-enabled suite: `5236 passed, 39 skipped in 99.22s`, 87% total coverage
- no live/network/paid provider, xLights, audio, commit, or integration action

AC2 is owner-amended: P3-T4's boundary is recursive mutation-discriminating typed/by-name
projection, prompt, cache, and validation consumption of every contract leaf. P3-T5
remains the first emitted-behavior consumer for `call_response_pairs` and
`coordination_intent` and remains unauthorized. This amendment resolves P3-T4's prior
binding contradiction without authorizing P3-T5 or inventing a fake behavioral sink.

### Narrow ChoreoTag re-review remediation

A narrow re-review correctly rejected the first remediation's global reinterpretation of
`PlanTarget(type=ZONE)` as physical `GroupPosition.zone` / `DisplayZone`. The established
contract is `ChoreoTag`: `HOUSE`, `YARD`, `ROOF`, and `PERIMETER` select groups through
`ChoreoGroup.tags`. Physical spatial zones remain separate metadata and are neither
advertised nor accepted as plan-target zones merely because they exist on a position.

Red-first evidence was `5 failed, 3 passed`: legacy `HOUSE` tag expansion returned no
groups, a physical `HOUSE` position was incorrectly selected, physical-only `ACCENT`
was accepted, unified expansion failed, and macro validation rejected the tag target.
After restoring ChoreoTag-derived advertisement, validation, prompt summaries, focus
resolution, and expansion, the discriminator passed `8/8`. The recursive leaf registry
is additionally derived from Pydantic model annotations, so adding any nested contract
leaf without a named reader now fails mechanically.

Fresh post-re-review gates:

- focused contract/macro/group/MH/display: `494 passed in 1.85s`
- repository formatting/lint: `1343 files already formatted`; Ruff clean
- mypy: `Success: no issues found in 720 source files`
- immutable goldens: `73 passed, 8 skipped in 2.11s`
- relevant broad suite without coverage: `5238 passed, 39 skipped in 77.14s`
- `git diff --check`: clean

LOCAL-ONLY: on 2026-08-16 the owner authorized this P3-T4 probe only: confirm that the
configured planner model can produce the new schema (structured-outputs shape and
cross-reference validity). **Hard cap: at most 3 live macro-planner attempts on one
song.** The authorization does not cover P3-T5, xLights, audio mutation, or any other
live task. Attempt 1 was executed only after the orchestrator's harness-audit GO and was
rejected at the provider schema boundary as recorded below. Record each attempt and the
final outcome (accepted / repaired / refused); a contract the model cannot fill is a
contract defect.

The dedicated harness is now implemented at
`twinklr.core.agents.sequencer.macro_planner.live_probe`, with CLI module
`twinklr.cli.p3_t4_macro_probe` and the tracked one-song
descriptor `tests/fixtures/p3_t4_macro_probe/context.json`. It invokes the shipped macro
prompt through `AsyncAgentRunner`, builds prompt variables through
`MacroPlannerOrchestrator`, and runs the same external audio/catalog/target-graph
validator as production. Its frozen identity is model `gpt-5.6-sol`, default endpoint
`https://api.openai.com/v1`, schema hash
`5f0f842f98d7a27dec1d0f5eebe9f6549bb9ddb95930e1b4e47960cbea7d18d8`, provider
response-format schema hash
`b814e8b70cbfbacdaa2e5752cefc001249f03bfcd111245bc2d6b2006641b012`, and prompt hash
`166a109923323ef7df0a62a0424677782a5033102e748f4007fa9cdfd0a9038e`.

The CLI fails nonzero unless `--live`, `OPENAI_API_KEY`, exact audited HEAD and transitive
source-tree hashes, and sufficient explicit USD preauthorization are all present. It
uses the single canonical owner ledger under `~/.local/state/twinklr/owner-probes/`;
callers cannot select a second path to reset the cap. The ledger is locked nonblocking,
tamper-evident, rejects symlinks, counts identity changes toward the same three-attempt
limit, and becomes terminal after a success. Each invocation is pinned to one provider attempt,
zero SDK retries, no compatibility fallback, and zero schema repair requests. A durable
atomic evidence record is written before the request (so a crash consumes the attempt),
and no fourth task attempt is permitted. The evidence records source/input/prompt/schema
identity, command/timestamps, response identity/mode, exact token classes, frozen-price
cost, external validation, and outcome. The rendered serialized request is hashed and size-bounded before provider
construction; its conservative token bound plus the frozen output budget must fit the
USD cap. Provider entry is counted before awaiting transport, and success requires exact
response ID/model/json-schema mode/schema hash/finish/fallback metadata. The provider
captures the service-reported response model; a requested-model fallback is marked as
non-actual and cannot pass the probe. Offline
fake-provider tests cover fail-before-call, global cap/terminal success/tampering,
request bounds, exact single-request transport settings, wrong response metadata,
transport failure counts, and both passing and failing evidence.

### Live attempt 1 and schema-boundary remediation — 2026-08-16

After explicit GO, the audited harness entered the provider exactly once. OpenAI returned
HTTP 400 `invalid_json_schema` at the schema path for `ThemeRef.scope`: the emitted node
combined `$ref` with the annotation sibling `description`, which the provider forbids.
No provider retry, JSON-object fallback, or schema repair request occurred. Provider usage
was unavailable, so the canonical ledger correctly retained the complete `$1.66`
reservation. The remaining `$0.09` under the cumulative `$1.75` task cap cannot authorize
another `$1.66` worst-case reservation, even though the separate three-attempt count was
not reached. The failed evidence and ledger are owner-local and must remain untouched.

The offline remediation is a general machine transform in `schema_utils`, not a
MacroPlan-specific edit. Every `$ref` node is reduced to the reference alone when its
siblings are non-semantic annotations (`description`, `title`, `default`, and the other
standard annotation keywords); a semantic constraint sibling fails loudly rather than
being discarded. Recursive tests audit every registered response root, discriminate the
exact `MacroPlan -> ThemeRef.scope` case, and assert the OpenAI provider sends the exact
normalized format whose hash also participates in cache identity. The remediated
serialized request hash is
`ca9147ba044b347d036a222f0e32b1073e674b5be6efd1387d264e9ecce361c0`
at `38236` bytes. This offline result does not satisfy live acceptance; that criterion
remains open with no further attempt funded under the accepted cap.

The frozen request budget is temperature `0.7`, reasoning effort `high`, timeout `60s`,
maximum output `8000` tokens, and a conservative serialized prompt/request ceiling of
`70000` bytes/tokens. Frozen conservative pricing is `$10/M` prompt and `$60/M` for each
reasoning/completion class. Its worst-case preauthorization is `$1.66`; the hard
cumulative budget for the entire P3-T4 task is `$1.75`, not `$1.75` per attempt. The
canonical ledger records actual, reserved, and committed spend and refuses a next
attempt unless committed spend plus another `$1.66` reservation fits under `$1.75`.
The reservation converts to actual spend only when response metadata supplies
provider-marked explicit, nonnegative, nonzero, internally consistent
prompt/reasoning/completion/total usage that agrees with runner attribution and stays
within the frozen bounds. Missing, default-zero,
partial, inconsistent, or out-of-bound usage is recorded as `usage_unavailable`; the full
`$1.66` remains committed permanently.

The eventual GO command must invoke the frozen environment with
`uv run --locked python -m twinklr.cli.p3_t4_macro_probe ...`; the CLI's required arguments are `--live`,
`--expected-source-sha`, `--expected-source-tree-hash`, `--expected-input-hash`,
`--expected-catalog-hash`, `--expected-request-hash`, and `--preauthorize-usd`.
The harness additionally verifies the frozen Python/OpenAI/Pydantic versions from the
tracked probe descriptor before provider construction. It strictly loads and hashes the
tracked `catalog/templates/` store and refuses any ignored `data/templates/` overlay.
`source_tree_hash` is the digest of the explicit transitive `source_files` manifest in
the evidence, not a claim to hash every dirty-worktree byte. Probe identity relies on
that audited manifest plus the separate input, catalog, and serialized-request pins.

Fresh post-harness-remediation offline gates (2026-08-16): dedicated adversarial harness
`37 passed`; focused macro contract/harness `60 passed`; relevant
macro/group/moving-head/display/provider regression `534 passed`; immutable goldens `73 passed,
8 skipped`; repository Ruff clean and `1346 files already formatted`; mypy clean across
`722 source files`; full suite `5276 passed, 39 skipped`. Earlier broad runs exposed and
then drove fixes for model-literal centralization and core logging policy; the quoted full
repo-hygiene policy failures and drove fixes; the quoted full result is the fresh post-fix
rerun. No live provider was contacted by any gate.

Fresh post-attempt schema-remediation gates (2026-08-16): the three red discriminators
failed before the transform (registered-root `$ref` sibling, semantic-sibling fail-loud,
and exact MacroPlan `ThemeRef.scope`) and pass after it. Strict-schema/provider/contract/
harness focused suite: `122 passed`; complete P3-T4 planning/provider surface: `638
passed`; immutable goldens: `73 passed, 8 skipped`; Ruff clean and `1346 files already
formatted`; mypy clean across `723 source files`; full offline suite: `5280 passed, 39
skipped`. Frozen remediated identities are source SHA `33cce5793fe5465c9d097dc131e8d08ec42f72b5`,
explicit transitive source-manifest hash
`d424435c62c4486c6c0ed1fc77029b46109edb00575a4e53ce934f1f0b451f08`, schema hash
`5f0f842f98d7a27dec1d0f5eebe9f6549bb9ddb95930e1b4e47960cbea7d18d8`, response-schema
hash `b814e8b70cbfbacdaa2e5752cefc001249f03bfcd111245bc2d6b2006641b012`, prompt hash
`166a109923323ef7df0a62a0424677782a5033102e748f4007fa9cdfd0a9038e`, input hash
`b85ffec41c133f9ccbe3c1af0e91ec4ca861360e9224150cd8f0614c1a24d261`, catalog hash
`35c62d4ab3534e8d9a026fa699caeab739d279fec91e2be56fc98ad220a4bf5e`, and serialized
request hash `ca9147ba044b347d036a222f0e32b1073e674b5be6efd1387d264e9ecce361c0`
(`38236` bytes). All gates were locked and offline; no second provider call was made.

### Integration record — 2026-08-16

The owner-approved exact contract/invariants and AC2 amendment, including the general
post-attempt `$ref` remediation, received independent offline and code approvals and were
integrated at `558153c`. This closes P3-T4's implementation/offline-verification boundary,
not its live acceptance boundary. Attempt 1 remains the only authorized live evidence:
HTTP 400 `invalid_json_schema`, no retry/fallback/schema repair, usage unavailable, full
`$1.66` reservation committed, and `$0.09` remaining. At that 2026-08-16 boundary, live
acceptance remained open and no further P3-T4 live attempt was authorized. The owner's
then-current “continue” separately authorized P3-T5 as the next offline task only; it did
not waive earlier empirical exits or authorize P3-T5 live work, P3-T6+, or any paid/local
empirical action. The 2026-08-26 amendment below supersedes only that live-attempt and
downstream-authorization state.

### Owner-authorized second-attempt amendment — 2026-08-26

The owner authorized exactly one additional audited P3-T4 live request under
authorization ID `p3-t4-second-attempt-owner-approved-2026-08-26`. This amendment sets
an exact two-attempt lifetime cap and raises the cumulative hard cap to `$3.32`:
attempt 1's permanently committed `$1.660000` plus exactly one new `$1.660000`
preauthorization. It does not authorize a third attempt under any outcome or metered
cost.

The amendment is bound to the existing canonical owner ledger and integrity key. Before
attempt 2 can be recorded, the harness requires the prior unsigned-ledger hash
`97c38f6c4bd2facc7bfc0488a991ac79e0d454e04fb177728317224a32babcdc` and prior-attempt
hash `29802ebe121b5284e33d201bf79df7ee6901bf33204765ca5b43487a6d33b562`, then verifies
one failed attempt, one provider entry, no logical retry, unavailable usage, no success,
and recomputed `$1.660000` committed spend. Missing/reset/resealed-but-changed history
fails closed and can never initialize a fresh ledger. The sealed authorization amendment
and in-progress attempt 2 are one atomic transition; attempt 1's canonical object remains
unchanged. The source manifest must also be clean and committed before any request.

The amendment implementation and offline adversarial suite were independently audited
after the clean-manifest remediation below. The CLI adds required authorization ID,
prior-ledger-hash, and prior-attempt-hash inputs alongside the existing identity pins.
Its single authorized execution and sealed outcome are recorded below.

Fresh offline author gates for the pre-execution amendment candidate: dedicated adversarial
harness `50 passed`; broader macro/group/provider/schema/coordination regression `408
passed`; repository format `1361 files already formatted`; Ruff clean; mypy clean across
`731 source files`; full offline suite `5365 passed, 38 skipped`; `git diff --check`
clean. No provider/network/live call was made by any gate.

#### Independent preflight rejection and remediation

Independent review rejected candidate `f0557b9` because its clean-manifest check used
`git status --untracked-files=no`. An untracked repository-root `sitecustomize.py` or an
untracked file beneath a transitive source root could therefore influence Python import
or probe behavior without failing preflight. The rejected commit remains audit history
and is not an executable candidate.

Two public-seam discriminators reproduced the bypass (`2 failed`): one root bootstrap
file and one file under `packages/twinklr/core/agents/providers/`. The remediation uses
`--untracked-files=all`, and both discriminators now pass. Ignored owner-local files
remain governed by the existing explicit overlay checks; every non-ignored untracked
path now makes the repository manifest dirty. No provider/network/live call or canonical
ledger mutation occurred during review or remediation.

Fresh remediation author gates: dedicated harness `52 passed`; repository format `1361
files already formatted`; Ruff clean; mypy clean across `731 source files`; full offline
suite `5367 passed, 38 skipped`; `git diff --check` clean.

### Live attempt 2 and provider-capability remediation — 2026-08-26

After independent audit and clean-commit preflight, the amendment executed its one
authorized request. OpenAI returned HTTP 400 `invalid_request_error` with parameter
`temperature`: `temperature` is not supported by `gpt-5.6-sol`. The sealed attempt-2
record contains exactly one provider entry, zero logical requests, zero retries, zero
JSON-object fallbacks, zero schema repairs, no response metadata, and unavailable usage.
The full second `$1.660000` reservation therefore remains committed. Together with
attempt 1, canonical spend is `$3.320000` reserved and committed, with no trustworthy
actual usage. The two-attempt lifetime cap is exhausted. No third attempt is authorized
under any outcome, remediation, price change, or later invocation; live acceptance
remains open.

The offline root-cause remediation makes `temperature` optional through `AgentConfig`,
`AgentSpec`, logging, and runner/orchestrator seams and centralizes OpenAI optional
generation parameters in an explicit model-capability policy. `gpt-5.6-sol` now omits
temperature while retaining its configured reasoning effort; known
temperature-supporting models still receive their configured temperature. The runner,
provider request, serialized request evidence, and probe identity all consume the same
normalized configuration, preventing audit identity from diverging from actual provider
parameters. A provider HTTP 400 for an unsupported parameter remains terminal even when
provider retries and JSON-object fallback are otherwise enabled.

TDD discriminators captured the pre-fix failures at the public provider, runner, and
probe serialization/identity seams, then passed with the shared normalization. Further
tests pin optional config/spec temperature, a known temperature-supporting model, the
preserved reasoning-effort parameter, and the one-request terminal unsupported-parameter
path. No provider/network/live call or canonical-ledger mutation occurred while
authoring or testing this remediation. It is offline remediation only and cannot convert
either failed request into live acceptance or create attempt 3.

Fresh post-call remediation gates: provider/runner/config/probe focused suite `149
passed`; full offline suite `5373 passed, 38 skipped`; repository format `1362 files
already formatted`; Ruff clean; mypy clean across `732 source files`; and `git diff
--check` clean.

## Effort & risk

**Size: L.** Design-bearing, touches the schema seam three other tasks build on.

**Main risk: designing a second generation of unread fields.** The whole finding class
here (F1, F12, CF-3) is "solicited output with no sink". Adding `focal_roles` and
`call_response_pairs` without P3-T5 consuming them would reproduce it exactly, one
phase later. *Mitigation*: acceptance criterion #2 is mechanical and blocking, and
P3-T5 depends on this task specifically to consume the new fields — if P3-T5 slips,
this task's fields do not ship.

**Secondary risk: the model can't produce it.** A richer, cross-referenced schema is
harder for the planner to fill correctly, and the repair loop is weak (P3-M-D: ONESHOT
repair never shows the model its failing output; P2P-T9 fixes that). *Mitigation*: the
LOCAL-ONLY live probe is a required deliverable, not optional; if the model struggles,
simplify the cardinalities (fewer required cross-references) rather than making fields
optional-and-unread.

**Third risk: cache identity.** `MacroPlannerOrchestrator.get_cache_key` serializes the
whole plan; changing the model invalidates cached macro plans. This is a clean miss
that regenerates (same reasoning as the fingerprint addendum's "M1 retarget SAFE") —
note it, do not engineer around it.
