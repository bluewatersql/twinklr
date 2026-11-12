---
type: plan
status: proposed
area: engineering
created: 2026-11-12
updated: 2026-11-12
---

# P0 Behavior Contracts and Reference Cases Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task.
> Steps use checkbox (`- [ ]`) syntax for tracking. This document authorizes no execution.

**Goal:** Make legacy behavior, requested-but-ineffective controls, and comparison
inputs explicit before changing rendered output.

**Architecture:** Keep the current rendering path intact. Add a versioned render-policy
selection, structured diagnostics and functional identity, then extend synthetic test
support and compose a restrained reference policy from the existing catalog/selector.

**Tech Stack:** Python 3.13, uv, Pydantic V2, pytest; existing renderer and catalog.

**Spec:** [Shared contracts](architecture.md), [report §8 P0](../report.md#phase-p0--establish-the-behavior-contract-and-reference-cases).

## Global constraints

- Python 3.13 only; uv workspace; Pydantic V2 for public/LLM-facing data.
- `legacy_v1` remains the default; physical behavior changes require explicit opt-in.
- The emitted effect grid remains 20 ms; timing markers remain source-exact.
- No project source is changed while preparing this plan; all tasks below are future work.
- Read all [shared requirements](architecture.md#1-goals-and-boundaries).

## Review focus

1. Old jobs must not accidentally select new behavior — T1 compatibility tests.
2. Claimed 16-bit/limit/intensity support must not hide ineffective output — T2 diagnostics.
3. A content-only preset edit must invalidate relevant render identity — T2 fingerprint tests.
4. Missing/odd-count fixtures and changing tempo must not be absent from the baseline — T3.
5. New reference policy must not change the frozen selector experiment — T4 regression.

## Technical design

### Baseline and policy

Current sources: [JobConfig](../../../packages/twinklr/core/config/models.py),
[render pipeline](../../../packages/twinklr/core/sequencer/moving_heads/pipeline.py),
[golden harness](../../../tests/golden/harness.py),
[selector](../../../packages/twinklr/core/agents/sequencer/moving_heads/deterministic_selector.py).
The old plan schema's omission provenance and accepted goldens remain authoritative
for legacy behavior. Do not regenerate them just because new physical math differs.

Proposed `MHRenderPolicy` has `mode: Literal['legacy_v1','physical_v2']='legacy_v1'`.
P1 adds the physical policy's supported settings. Add `JobConfig.moving_heads` with a
default factory and allow schema `3.0 | 3.1`, retaining `3.0` by default. Validate that
`physical_v2` requires `3.1`. Until P1 is integrated, requesting physical mode raises
an explicit unsupported-mode exception before rendering, never silently falling back.

### Diagnostics and fingerprint

Proposed `diagnostics.py` owns `MHDiagnostic` (frozen Pydantic model):
`code: str`, `severity: Literal['info','warning','error']`, `message: str`,
`fixture_id: str|None`, `section_id: str|None`, `channel: str|None`,
`action: Literal['unchanged','rejected','substituted']`. Codes are the shared contract's
bounded vocabulary; implement them as `Literal`/enum, not unconstrained arbitrary codes.

`audit_legacy_controls(plan: ChoreographyPlan, fixtures: FixtureGroup,
templates: Sequence[TemplateDoc]) -> tuple[MHDiagnostic, ...]` diagnoses only actually
requested ineffective fields, not every theoretical feature. Examples: fine channels
requested but not realized, movement intensity not reaching movement, declared limits
not guaranteeing dynamic curves, template floor metadata, and shutter intent above 16.
Diagnostics have deterministic ordering and do not mutate a plan or generated output.

`identity.py` owns `render_fingerprint(*, plan: BaseModel, beat_grid: BeatGrid,
fixtures: FixtureGroup, templates: Sequence[TemplateDoc], policy: MHRenderPolicy,
backend_id: str, renderer_revision: str, seed: int | None=None,
phase_map: BaseModel | None=None) -> str`. The optional phase map is P1's typed boundary
map; P0 accepts a BaseModel to avoid depending on a future implementation. Hash canonical JSON of functional
inputs, including template content, not just IDs. Include the 20 ms grid and emitted
version stamp. Treat diagnostic wording/output paths as nonfunctional; motion/profile,
ordering, seed and preset changes are functional. Legacy artifacts need no new cache
read path; record the fingerprint in the new research/physical manifests first.

### Synthetic matrix

Reuse golden harness construction patterns without loading local fixture files.
New support module `tests/support/mh_true_up.py` provides
`synthetic_case(case_id: str) -> SyntheticMHCase` containing a plan, BeatGrid, fixture
group and expected-case metadata. Explicit cases:

| Case | Content | What it exposes |
|---|---|---|
| `counts` | 1,2,3,4,6,8 fixtures with stable IDs | Role/topology and subset behavior |
| `fine_carry` | Nonadjacent coarse/fine mappings | 255→256 word carry and inversion |
| `channel_edges` | Shutter17, final supported48, unsupported49 | Backend versus old intent ceiling |
| `tempo` | Beat ms `[0,500,1000,1500,2000,2400,2800,3200,3600]`; bars `[0,2000,3600]` | Exact internal musical phase |
| `meter3` | Three beats per bar; constant beat interval | No assumed four-beat subdivision |
| `finite` | Non-closing fade, one-shot accent, section shorter than cycle | End-state/wrap semantics |
| `state` | Unknown initial pose, known darkness, too-short dark gap | Honesty about feasibility |
| `locks` | Motion locked while intensity changes | Future boundary/lock checks |

Matrices specify synthetic speed/range values as test inputs, not calibration facts.
Physical cases can be model-validation fixtures until P1 supplies the compiler; do
not mark unimplemented physical behavior passing or permanently xfail its desired tests.

### Restrained reference policy

The existing selector and `three_arm.py` contain fixed experiment policies. Preserve
them. Add a separate **reference policy adapter**, sharing catalog lookup, candidate
resolution and validation rather than changing those fixed defaults. Use deterministic
preferred existing templates: quiet sections `hold_center_out_breathe`, choruses
`sweep_lr_pingpong_phase`, section-entry emphasis `sweep_lr_fan_hold`, ending
`wave_scattered_fade_out`. A preference is filtered against admitted capabilities and
catalog availability; missing preference uses the existing selector's candidates with
stable seeded order and an explicit trace. No eligible template is an error.

This is a restrained comparison using existing templates, **not a claim to reproduce
xLights' precise envelopes**, which would require new components in P2. Label its arm
`reference_legacy_v1`; a later physical reference has its own fingerprint/arm identity.
No LLM calls, heuristic retuning after seeing comparison scores, or old-experiment edits.
Preference precedence is final section → ending template; chorus/drop/peak role →
chorus template; build/lift role → entry-emphasis template; energy≤33 → quiet
template; otherwise unchanged candidate-helper fallback. This is a declared policy,
not a classifier inferred from section display names.

## Implementation tasks

### P0-T1 — Render-policy compatibility boundary

**Files:** Modify `packages/twinklr/core/config/models.py` and
`packages/twinklr/core/sequencer/moving_heads/pipeline.py`; create
`tests/unit/config/test_mh_render_policy.py`.

**Interfaces:** Produces `MHRenderPolicy` and `JobConfig.moving_heads` described above;
consumes existing `JobConfig` and `RenderingPipeline` constructor.

- [ ] Write `test_omitted_policy_retains_legacy`: assert `JobConfig().schema_version == '3.0'`
  and `JobConfig().moving_heads.mode == 'legacy_v1'`; compare old golden output unchanged.
- [ ] Write `test_physical_mode_requires_schema_31` and
  `test_unimplemented_physical_mode_is_rejected`; no silent mode change or partial file.
- [ ] Run `uv run pytest tests/unit/config/test_mh_render_policy.py -q`; verify the new
  tests fail for missing behavior, then add the fields/validators and explicit dispatch.
- [ ] Rerun that command and `uv run pytest tests/golden/test_settings_golden.py -q`;
  expect all selected tests pass without `--regen-goldens`.
- [ ] Have a separate reviewer inspect the default-path diff; integrator commits
  `feat(mh): define versioned render policy without changing legacy output`.

### P0-T2 — Effective-control diagnostics and render identity

**Files:** Create `packages/twinklr/core/sequencer/moving_heads/diagnostics.py`,
`identity.py` in the same directory, and
`tests/unit/sequencer/moving_heads/test_render_identity.py`, `test_control_diagnostics.py`.
Modify the MH pipeline only to expose diagnostics/identity, not to repair controls.

**Interfaces:** Consumes T1 policy plus existing plan/grid/template/fixture models;
produces the audit and fingerprint functions above and an immutable diagnostics tuple.

- [ ] Write tests asserting fine-channel requests produce a named diagnostic; ordinary
  supported coarse-only output is unchanged; unavailable shutter intent is distinguished
  from an available default channel; source inputs are not mutated.
- [ ] Write identity tests: reorder irrelevant dict keys → same hash; change template
  content, fixture order, policy or BeatGrid → different hash; change output path → same
  hash. Assert `len(hash) == 64`, with deterministic results across repeated calls.
- [ ] Run `uv run pytest tests/unit/sequencer/moving_heads/test_render_identity.py tests/unit/sequencer/moving_heads/test_control_diagnostics.py -q`;
  confirm failures, implement canonical serialization/audit, rerun for PASS.
- [ ] Integrator commits `feat(mh): report effective controls and fingerprint render inputs`.

### P0-T3 — Reusable adversarial synthetic cases

**Files:** Create `tests/support/mh_true_up.py` and package initializer if absent;
create `tests/unit/sequencer/moving_heads/test_true_up_cases.py`. Reuse, do not replace,
`tests/golden/harness.py`/existing accepted golden files.

**Interfaces:** Produces `SyntheticMHCase` and `synthetic_case(case_id)`; fixture data
is constructed in memory and has no disk-local configuration dependency.

- [ ] Write case-contract tests asserting the exact tempo arrays above, unique ordered
  fixture IDs, intentional channel edges and nonadjacent byte mappings. Unknown case ID
  raises `ValueError`; fixture construction never reads environment/local config.
- [ ] Run `uv run pytest tests/unit/sequencer/moving_heads/test_true_up_cases.py -q`,
  verify missing-case failures, implement fixtures, rerun for PASS.
- [ ] Exercise legacy cases through the real pipeline and preserve existing snapshots;
  label physical-only fixtures as input definitions rather than completed behavior.
- [ ] Integrator commits `test(mh): add synthetic precision timing and state cases`.

### P0-T4 — Restrained reference arm without changing the old experiment

**Files:** Create `packages/twinklr/core/agents/sequencer/moving_heads/reference_policy.py`
and `tests/unit/agents/sequencer/moving_heads/test_reference_policy.py`.

**Interfaces:** `build_reference_plan(sections: list[SelectorSection], *, seed: int,
admitted_template_ids: frozenset[str]) -> ReferenceSelectionResult`; consume existing
catalog and selector helpers. Define frozen `ReferenceSelectionDecision(section_id,
preferred_template_id: str|None, selected_template_id, reason)` and
`ReferenceSelectionResult(plan: ChoreographyPlan, baseline: SelectorResult,
decisions: tuple[ReferenceSelectionDecision,...], seed: int,
policy_revision: Literal['reference.v1'])` in `reference_policy.py`. Preserve the
baseline object and its frozen trace model unchanged; the new wrapper owns preference
and substitution provenance. Never label the newly selected plan as the old experiment.

- [ ] Write tests for the preferred quiet/chorus/ending choices, identical seed/input
  reproducibility, filtered-out preference fallback, and no eligible template error.
  Assert the existing selector's output is unchanged for its original test inputs.
- [ ] Run `uv run pytest tests/unit/agents/sequencer/moving_heads/test_reference_policy.py -q`;
  verify failure, implement the adapter, then rerun with
  `tests/unit/agents/sequencer/moving_heads/test_deterministic_selector.py` and
  `tests/unit/reporting/evaluation/test_three_arm_experiment.py` included; expect PASS.
- [ ] Integrator commits `feat(mh): add a separate restrained reference policy`.

## Exit, rollback and next phase

Complete T1–T4, independent review, and clean-tree `make validate`; disclose any skipped
checks. No new physical correctness/taste claim follows from P0. Record effective
controls, fixture matrix and baseline fingerprints in a dated evidence record. Rollback
removes the opt-in additions without changing old plan/config/golden behavior.
P1 consumes the policy, diagnostics, identity and cases; P5 can begin its evidence
adapter once the frame contract is ready.
