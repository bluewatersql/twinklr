# P3-T4 — Macro structured contract (D3)

Phase: 3 (Show Convergence / M3) · Lane: W (wiring) · Executor: opus · Verifier: opus
· Depends on: P2P-T1 (plan schema v2), P3-T3

⚖ **Owner-decision-bearing.** This task defines the cross-element coordination
vocabulary the whole product's "part 2" rests on. The owner reviews: the field list
below (what a macro plan is allowed to say), the deletions from today's `MacroPlan`,
and the precedence rule between macro-level and section-level choices.

> **This spec is the single definition of the macro contract for the whole program.**
> `build/plan/06-phase-3-show-convergence.md` states it directly: "T4 is
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
`agents/shared` + schemas; `build/plan/04-phase-2p-creative-quality.md` notes "T1 and
T9 both touch `agents/shared`+schemas: T1 lands first; T9 rebases." The same applies
here: rebase on P2P-T1's schema work. If P2P-T1 introduced a macro-adjacent field that
duplicates one above, **this spec's name and shape win** and P2P-T1's is renamed to
reference it — that is the point of defining the contract once.

Deliverable beyond code: a decision record in `memories/decisions/` capturing the
contract, the deletions and why, and the precedence rule. Per `AGENTS.md`, that is
where durable decisions live; a docstring is not sufficient for a contract other specs
reference.

Sequencing constraints copied verbatim from `build/plan/00-overview.md`:

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

From `build/plan/06-phase-3-show-convergence.md`: Lane W is `T3 → T4 → T5`.

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

LOCAL-ONLY: one live macro-planner call to confirm the model can actually produce the
new schema (structured-outputs shape, cross-reference validity). **Test budget: at most
3 live macro-planner calls on one song, at the configured planner model.** Everything
else runs against fixtures at $0. Record the live call's outcome (accepted / repaired /
refused) in the PR body — a contract the model cannot fill is a contract defect.

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
