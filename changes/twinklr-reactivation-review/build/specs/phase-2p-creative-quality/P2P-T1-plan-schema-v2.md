# P2P-T1 — Plan schema v2

Phase: 2P (Creative Quality, Measured) · Lane: S (schema/channel, serial) · Executor: opus · Verifier: opus · Depends on: Phase 1P merge (all lanes)

⚖ **Owner-decision-bearing.** This task fixes the shape of the LLM→renderer contract
for the rest of the program. The owner reviews: (a) the final field list of
`PlanSection` v2, (b) the intent vocabulary chosen for intensity/color, and (c) the
deletion list (§ "The 20 dead solicited fields"). Everything else is executor
discretion within this spec.

## Objective

Widen the LLM→renderer channel from two free-form strings (`template_id`,
`preset_id`) to a typed intent contract: categorical intensity that the renderer
actually consumes, a color intent, shutter/gobo events, references to lyric
MomentCues, and optional segmentation — while deleting the solicited schema fields
that no consumer reads, and keeping every response model compatible with the strict
structured-outputs migration that lands in P2P-T11. After this task the *schema* can
carry creative intent; P2P-T2 makes the renderer resolve it.

## Evidence & background

Findings: **CF-3** (channel is two strings wide), **P3-F12** (20 dead solicited
fields), **P3-F14** (`recommended_sections` never rendered), **P4-F17**
(V-categorical: vocabulary never reaches MH rendering), **P4-F23** (only five plan
fields reach the renderer), **D1** (widen the channel).
Sources: `changes/twinklr-reactivation-review/reviews/phases/llm-agents-and-planning.md`
§4.6, §10 (P3-F12/F14); `.../phases/moving-heads-rendering.md` P4-F16/F17/F18/F23;
`.../reviews/modernization.md` M2; `.../reviews/reactivation-proposal.md` D1.

Verified mechanics the executor must not re-derive differently:

1. **Only five plan fields reach the renderer** (P4-F23, verifier-confirmed).
   `TemplateCompileContext` (`sequencer/moving_heads/pipeline.py:226-238`) is built
   from exactly `section_name`, `start_bar`, `end_bar`, `template_id`, `preset_id`.
   `modifiers`, `reasoning`, `section_role`, `energy_level`, `transition_out` are
   copied into the flattened `PlanSection` by `iterate_plan_sections`
   (`pipeline.py:303-313`) and **never read by anything** in `sequencer/`. A sixth,
   `transition_in`, is read at `pipeline.py:350` but is "almost certainly always
   `None`" because no planner prompt instructs a structured `TransitionHint`.

2. **Two unrelated intensity enums, no converter** (P4-F17, verified airtight):
   `Intensity` (`sequencer/models/enum.py:111`; SLOW, SMOOTH, FAST, DRAMATIC,
   INTENSE) and `IntensityLevel` (`sequencer/vocabulary/intensity.py:11`; WHISPER,
   SOFT, MED, STRONG, PEAK) are "two entirely separate enums with no conversion
   function anywhere in the repository". `Intensity.amplitude`
   (`models/enum.py:132`) — "a property that looks like the bridge" — has zero
   callers. The MH planner emits **no categorical value at all**: verified today,
   `PlanSection` (`agents/sequencer/moving_heads/models.py`) carries `section_name`,
   `start_bar`, `end_bar`, `section_role: str|None`, `energy_level: int|None`,
   `template_id: str|None`, `preset_id: str|None`, `modifiers: dict[str,str]`,
   `reasoning: str`, `segments: list[PlanSegment]|None`, `transition_in/out`.
   "**Not one field is typed with a vocabulary enum.**"

3. **`recommended_sections` is computed, carried, serialized, and dropped one line
   before the model sees it** (P3-F14, re-verified in this tree):
   `agents/sequencer/moving_heads/stage.py:238-239` populates it into
   `TemplateDescription`; `agents/sequencer/moving_heads/context.py:46` carries it;
   `prompts/planner/user.j2` emits only `td.template_id`, `td.description`,
   `td.energy_range`, `td.tags`. Grep-verified: `recommended_sections` appears in
   **zero `.j2` files repo-wide**. It is the exact join column that makes template
   selection decidable, and the LLM has never seen it.

4. **`PlanSection`'s either/or invariant is not expressible in strict JSON Schema**
   (§4.6). Today it is enforced by `_validate_section` (model validator) plus a
   heuristic check (`heuristic_validator.py:219-228`). Strict mode disallows a
   top-level union; the choices are a discriminated union under a `kind` field or
   accepting that the invariant stays a post-validation check.

5. **Methodological note from the P3-F12 verifier, binding on this task**: "a
   by-name grep is insufficient on this codebase. Field-consumption analysis must
   first enumerate whole-model `model_dump()` / `| tojson` sites and treat every
   field of those models as prompt-reachable." The three known whole-model dumps are
   `moving_heads/prompts/judge/user.j2:12`,
   `group_planner/prompts/section_judge/user.j2:93`,
   `group_planner/prompts/holistic_judge/user.j2:137`.

Line numbers are hints from baseline `aa8d325`; re-verify before editing.

## Current behavior

- The moving-head planner emits `template_id` + `preset_id` (+ inert prose fields)
  per section. The renderer reads five fields. Everything else the LLM produces is
  either re-serialized into another prompt or discarded.
- Categorical intensity exists twice, converts nowhere, and is not on the planner
  contract at all. Movement intensity is separately overwritten in the renderer
  (CF-1 — fixed in P1P-T3; this task must not re-break it).
- Color, gobo and shutter have no representation on the plan contract (P4-F16:
  0/37 templates reference them; `ColorLibrary`/`GoboLibrary`/`ShutterLibrary` have
  zero consumers).
- Lyric moments have no representation on the plan contract (see P2P-T4).
- 20 solicited response fields have no reader of any kind; a further 21 exist only
  to be pasted into the next model's prompt.
- Response models lean on optionality and `default_factory`, which strict structured
  outputs forbids.

## Target behavior

### 1. `PlanSection` v2 — typed intents

`PlanSection` gains typed, renderer-resolvable intent fields. Design decisions
already made (do not relitigate):

- **Intensity: ONE enum, actually wired.** Unify to a single categorical intensity
  on the plan contract. `Intensity` (`sequencer/models/enum.py`) is the enum the
  moving-heads renderer's parameter tables are already keyed by
  (`libraries/movement.py`, `libraries/dimmer.py`), so the plan-side field is typed
  with `Intensity` and `IntensityLevel` is **not** put on the MH plan contract.
  Whether `IntensityLevel` survives for the display side is out of scope here;
  `vocabulary/intensity.py::INTENSITY_MAP` and `resolve_intensity` are dead
  (P4-F20) and are deleted by this task.
- **Color intent: palette role OR explicit cue.** A `ColorIntent` model with a
  discriminated `kind` (`PALETTE_ROLE` | `EXPLICIT`), so strict mode can express it
  as an object with all fields required and the unused arm nulled.
- **Shutter/gobo: event lists, not curves.** A colour or gobo wheel is a discrete
  DMX index with a mechanical settling time, not a continuous curve (P4-F16's "one
  genuine design question"): model them as timed events referencing bar/beat
  positions, resolved against the beat grid by P2P-T2.
- **Lyric MomentCue references.** `PlanSection` (and/or `PlanSegment`) can reference
  MomentCue ids defined on the lyrics model by P2P-T4. This task defines the
  *reference* shape and its validation; P2P-T4 defines `MomentCue` itself and the
  prompt wiring. Coordinate: T4 depends on T1 and rebases if the reference shape
  moves.
- **Segmentation stays optional** but the either/or invariant is re-expressed per
  the strict-mode constraint below.

### 2. Prompts updated

- `recommended_sections` is rendered into the MH planner prompt's template-library
  block alongside `description`, `energy_range`, `tags`. This is a precondition for
  P2P-T13's fairness (the LLM arm is otherwise handicapped by a template bug, not
  evaluated).
- The prompt documents the new intent fields and the vocabulary each accepts. The
  schema/taxonomy auto-injection (`async_runner.py:93-97`, ST-1/P3-F35) means the
  enum values are injected automatically — **do not hand-author enum lists in any
  `.j2`**; that property is the strongest thing in the agent layer and must survive.

### 3. The 20 dead solicited fields — DELETE

The verified partition of the 50 solicited fields is **20 dead / 9 with real
readers / 21 prompt-rendered** (P3-F12, corrected at verification from the author's
"33"). Delete the dead tier. The verifier's enumerated list:

| # | Field | Defined at (verified in tree) |
|---|---|---|
| 1 | `PalettePlan.transition_notes` | `sequencer/planning/models.py:53` |
| 2 | `LayeringPlan.strategy_notes` | `sequencer/planning/models.py:249` |
| 3 | `LayerSpec.timing_driver` | `sequencer/planning/models.py:227` |
| 4 | `TargetSelector.coordination` | `sequencer/planning/models.py:195` |
| 5 | `CorrectionResult.correction_notes` | `sequencer/planning/group_plan.py:166` |
| 6 | `AudioProfileModel.agent_id` | `agents/audio/profile/models.py:355` |
| 7 | `AudioProfileModel.schema_version` | `agents/audio/profile/models.py:351` |
| 8 | `Structure.notes` | `agents/audio/profile/models.py:133` |
| 9 | `EnergyProfile.overall_mean` | `agents/audio/profile/models.py:232` |
| 10 | `EnergyProfile.energy_confidence` | `agents/audio/profile/models.py:234` |
| 11 | `EnergyPoint.energy_0_1` | `agents/audio/profile/models.py:151` |
| 12 | `CreativeGuidance.recommended_asset_usage` | `agents/audio/profile/models.py:300` |
| 13 | `LyricContextModel.vocal_coverage_pct` | `agents/audio/lyrics/models.py:225` |
| 14 | `LyricContextModel.timed_word_coverage_pct` | `agents/audio/lyrics/models.py:229` |
| 15 | `LyricContextModel.vocal_presence_pct` | `agents/audio/lyrics/models.py:236` |
| 16 | `JudgeVerdict.overall_assessment` | `agents/shared/judge/models.py:82` |
| 17 | `JudgeVerdict.score_breakdown` | `agents/shared/judge/models.py:88` |
| 18 | `Issue.estimated_effort` | `agents/issues.py:215` |
| 19 | `Issue.suggested_action` | `agents/issues.py:227` |
| 20 | `Issue.scope` | `agents/issues.py:216` |
| 21 | `HolisticEvaluation.score_breakdown` | `group_planner/holistic.py:77` |
| 22 | `HolisticEvaluation.recommendations` | `group_planner/holistic.py:89` |

**Known arithmetic discrepancy — resolve it, don't paper over it.** The verifier's
*count* is 20 and carries authority; the enumerated list above expands to **22**
named fields (the review writes several as brace groups). The verifier explicitly
scoped its own authority: "the three bucket **counts** (20/9/21) carry the
verifier's authority; individual bucket assignments at that boundary do not," and
named the audio-profile echo fields as the unsettled boundary. Procedure:

1. Enumerate every whole-model `model_dump()` / `| tojson` render site across all
   11 prompt packs **first** (the three known ones are listed above; confirm no
   fourth has appeared).
2. For each of the 22 candidates, grep for (a) non-test Python readers and (b)
   prompt renders including via a whole-model dump.
3. Delete only fields that fail both. Record the final count and the per-field
   verdict in the task's handoff. If the honest count is 21 or 22 rather than 20,
   say so with evidence — do not delete a field with a reader to hit a number, and
   do not keep a dead field to hit one either.

**Two fields need more than a deletion.** `Issue.estimated_effort`,
`Issue.suggested_action` and `Issue.scope` are **required** fields with zero
readers, but deterministic code *constructs* Issues with them
(`agents/issues.py:198-205`, `group_planner/holistic.py:370-377`,
`macro_planner/heuristics.py:110-117`). Deleting the fields requires updating those
constructors in the same change.

**Do NOT delete the 9 with real readers**: `ChoreographyPlan.overall_strategy`
(`cli/main.py:281`); `PlanSection.section_role`, `.energy_level`, `.transition_out`,
`.reasoning` (`reporting/evaluation/generator.py:68,69,77,73`);
`PlanSegment.reasoning` (`generator.py:617`); `PlanSection.modifiers` and
`PlanSegment.modifiers` (`generator.py:591,616`, `compliance.py:57`); and
`MacroPlan.asset_requirements` (`macro_planner/heuristics.py:324,492`).
`MacroPlan.asset_requirements` is a special case the review resolved explicitly: the
prompt forbids emitting it (`macro_planner/planner/developer.j2:72-73`) while a
heuristic validates its contents — "the right remediation is deletion of the field
*and* its validator, not deletion of an unread field." Deleting that pair is **in
scope**; deleting the other eight is not.

### 4. Strict-structured-outputs constraints the new schema MUST satisfy

From `modernization.md` M2 and P3-F25/§4.6, verified against
developers.openai.com/api/docs/guides/structured-outputs (accessed 2026-08-13). The
new schema is designed for these now so P2P-T11 is a migration, not a redesign:

- **Object root only.** No top-level union, no top-level array.
- **All fields required.** Every property appears in `required`. Optionality is
  expressed as `X | null` (Pydantic `X | None` with **no default**), and the model
  is obliged to emit the key explicitly. This means removing `default_factory=list`
  and bare `= None` defaults across the planner response models
  (`PlanSection.segments`, `.preset_id`, `.modifiers`, `.transition_in/out`,
  `MacroPlan.asset_requirements`, `SectionCoordinationPlan.deviations`, …).
- **`additionalProperties: false` everywhere** — every nested object, not just the
  root. Pydantic: `ConfigDict(extra="forbid")` on every response model.
- **No `allOf`.** Avoid model inheritance that Pydantic renders as `allOf`; prefer
  flat composition or `$defs` + `$ref`.
- **Ceilings**: ≤5 000 properties, ≤10 nesting levels, ≤1 000 enum values. Current
  worst nesting is ~4–5 (`MacroPlan → layering_plan → layers[] → target_selector →
  roles[]`) and the categorical enums are far under 1 000 — the new intent fields
  must not blow past either.
- **The either/or invariant**: express `template_id` XOR `segments` as a
  discriminated union under a `kind` literal field (both arms present, unused arm
  nulled), OR keep it as a post-validation check and accept that some repair surface
  survives. **Decide explicitly and write the decision into the model docstring**;
  the review flags this as "the genuinely awkward one" and P2P-T11's promised
  retry-surface reduction depends on which way it goes.
- **Framework-populated fields** (`provenance`, `run_id`,
  `SectionCoordinationPlan.start_ms/end_ms`) currently appear in the injected schema
  while the prompt says not to emit them (P3-F16). Under all-fields-required this
  contradiction becomes a hard failure. Either exclude them from the response model
  entirely (preferred) or pass `exclude_fields` to
  `schema_utils.get_json_schema_example` (the parameter exists; grep-verified no
  caller passes it).

### Non-goals

- Renderer resolution of the new intents — that is **P2P-T2**. This task may add
  the fields and leave the renderer ignoring them for one merge, provided golden
  output is byte-identical (see acceptance criteria).
- Defining `MomentCue` itself and the lyrics prompt fix — **P2P-T4**.
- The actual `json_schema`/`responses.parse` migration — **P2P-T11**.
- Judge feedback/threshold repair — **P2P-T9** (it rebases on this task).
- Display-side (`SectionCoordinationPlan`, group planner) schema redesign. Dead-field
  deletions listed above that live in display-side models are in scope; redesign is
  not.

## Implementation approach

Files/symbols (re-verify line numbers first):

- `packages/twinklr/core/agents/sequencer/moving_heads/models.py` — `PlanSection`,
  `PlanSegment`, `ChoreographyPlan`.
- `packages/twinklr/core/sequencer/models/enum.py` — `Intensity` (the surviving
  enum); delete `Intensity.amplitude` (zero callers, P4-F20).
- `packages/twinklr/core/sequencer/vocabulary/intensity.py` — delete `INTENSITY_MAP`
  and `resolve_intensity` (dead per P4-F17/F20).
- `packages/twinklr/core/agents/audio/profile/models.py`,
  `packages/twinklr/core/agents/audio/lyrics/models.py`,
  `packages/twinklr/core/agents/shared/judge/models.py`,
  `packages/twinklr/core/agents/issues.py`,
  `packages/twinklr/core/sequencer/planning/models.py`,
  `packages/twinklr/core/sequencer/planning/group_plan.py`,
  `packages/twinklr/core/agents/sequencer/group_planner/holistic.py` — dead-field
  deletions + constructor updates.
- `packages/twinklr/core/agents/sequencer/macro_planner/heuristics.py` — delete the
  `asset_requirements` validator with the field.
- `packages/twinklr/core/agents/sequencer/moving_heads/prompts/planner/{user,developer}.j2`
  — render `recommended_sections`; document the intent fields.
- `packages/twinklr/core/agents/sequencer/moving_heads/stage.py` /`context.py` — no
  change needed for `recommended_sections` (already carried); verify.

Sequencing constraints copied verbatim from the plan:

> - T1 and T9 both touch `agents/shared`+schemas: T1 lands first; T9 rebases.
> - **Verification currency**: evidence in specs is from baseline `aa8d325`.
>   Executors must re-verify cited line numbers before editing (the tree will drift
>   as phases land) — specs cite symbol + file, with line numbers as hints only.
> - `make validate` equivalents (check-only forms until P0-T4 lands the guard) must
>   pass at every merge; golden tests (once P1P-T1 exists) must pass for any lane
>   touching render/export code.

Cache interlock (from the cache-fingerprint addendum, live once P1P-T9 lands):
prompt-pack content is hashed into agent-stage cache keys after P1P-T9, so the
prompt edits in this task invalidate correctly. Confirm P1P-T9 is merged before
relying on that; if it is not, bump the affected stages' `cache_version` literal by
hand and say so in the handoff.

## Acceptance criteria

1. `PlanSection` v2 carries, with types: one categorical intensity typed with
   `Intensity`; a `ColorIntent`; shutter and gobo event lists; MomentCue references;
   optional segments. Every new field is documented in the model docstring with the
   renderer-side resolution it expects.
2. `model_json_schema()` for `ChoreographyPlan`, `AudioProfileModel`,
   `LyricContextModel`, `JudgeVerdict` and `MacroPlan` satisfies every strict-mode
   constraint in §4: object root, all properties in `required`,
   `additionalProperties:false` at every level, no `allOf`, within all three
   ceilings. A test asserts this mechanically (see Tests).
3. Every field in the final deletion list has zero non-test Python readers and zero
   prompt renders (including whole-model dumps) at merge time, evidenced per field
   in the handoff. The 9 reader-bearing fields are untouched except the
   `MacroPlan.asset_requirements` + validator pair, which is deleted together.
4. `recommended_sections` renders into the MH planner prompt. A prompt-render test
   asserts the rendered text contains it for a fully-populated context.
5. No hand-authored enum list appears in any `.j2` (schema/taxonomy auto-injection
   remains the only source).
6. **Golden-diff BEFORE/AFTER: byte-identical.** This task changes the contract, not
   the render. Running the P1P-T1 golden suite over the tracked fixture rigs
   produces identical `E_SLIDER_DMX`/`E_VALUECURVE_DMX` settings strings before and
   after. Any diff is a defect in this task, not an expected consequence.
7. `make validate` check-only forms pass; no new mypy errors.

## Tests

TDD — write these failing first:

1. `test_plan_schema_v2_strict_mode_compatible` — walks
   `model_json_schema()` for each response model and asserts: root `type: object`;
   for every object node, `required` == the full property set and
   `additionalProperties is False`; no `allOf` key anywhere; property count,
   nesting depth and max enum length under the ceilings. This is the test that keeps
   P2P-T11 cheap.
2. `test_plan_section_v2_carries_typed_intents` — constructs a `PlanSection` with
   intensity/color/shutter/gobo/MomentCue-reference values and asserts round-trip
   through `model_validate_json`.
3. `test_plan_section_either_or_invariant` — pins whichever encoding was chosen
   (discriminated union or post-validation), including the failure message.
4. `test_deleted_fields_are_gone` — asserts each deleted field name is absent from
   the model's `model_fields`, so a re-introduction fails loudly.
5. **`test_every_pack_renders_against_populated_context`** — the test P3-F34 says
   "would have caught all three" silent-success defects: render every prompt pack
   against a fully populated context and assert on the *rendered output*. For this
   task, assert `recommended_sections` values appear in the MH planner user message.
   Extend it in P2P-T4 for the lyric block. Put it somewhere both tasks can share
   (`tests/unit/agents/prompts/`).
6. Golden render tests from P1P-T1 must pass unchanged (criterion 6).

## Verification commands

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy .
uv run pytest tests/unit/agents -q
uv run pytest tests/unit/sequencer -q
uv run pytest -k golden -q          # P1P-T1 golden render suite — must be byte-identical
```

No paid API calls. No `LOCAL-ONLY` steps in this task.

## Effort & risk

**L.** Main risk: the all-fields-required rewrite touches essentially every planner
model, and a mechanical `X | None` sweep can silently change runtime behavior where
a `default_factory=list` was load-bearing (code doing `for x in plan.modifiers`
now meets `None`). Mitigation: make the strict-mode sweep a separate commit within
the task, run the golden suite after it alone, and add `| None` handling at each
consumer rather than re-adding defaults. Second risk: deleting a field the sweep
called dead but a whole-model dump renders — mitigated by the mandatory
dump-enumeration step (§3, procedure step 1), which is exactly how the original
33→20 miscount happened.
