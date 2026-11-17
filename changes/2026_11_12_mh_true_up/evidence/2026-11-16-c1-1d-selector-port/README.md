---
type: review
status: complete
area: engineering
change: 2026_11_12_mh_true_up
created: 2026-11-16
updated: 2026-11-16
---

# C1.1d: deterministic selector and three-arm experiment on the admitted families — 2026-11-16

Cutover step C1.1d ([phase 3](../../plan/phase-3-arrangement.md#look-accepted-cutover-started--2026-11-16),
[inventory](../../plan/cutover-inventory.md) F6, F7, §3). Built test-first on
`feat/mh-cutover-selector` from `b5cbc658`. One implementing agent; not yet reviewed.
No provider call, owner data, xLights or sealed record was used.

## What the experiment was, and what was not touched

The three-arm experiment (P2P-T13) is code only: arm A the deterministic selector, arm
B the full LLM planner, arm C the LLM planner without the macro stage. It has never been
run; its manifest, results, blind ranking and D1 verdict are `PENDING-OWNER` (its spec's
"Truthful non-result"). No ledger, result or evaluation record exists, so nothing sealed
was edited or rerun. The P2P-T13 spec stays as history.

The families already carry everything the role/energy ladder reads (`category`,
`metadata.recommended_sections`, `metadata.energy_range`), so no family metadata and no
planner-visible byte was added.

## Behaviour

- **Candidate set.** `DeterministicSelector(admission=...)` chooses only among a
  `SelectorAdmission`, built from the gate's `TemplateAdmission` by
  `SelectorAdmission.from_gate`: the admitted templates in gate order, each with its
  effective variant and admitted presets, and the whole-family exclusions with reasons.
  A selected section names the family's effective variant as `preset_id` (None for the
  base), the variant a section naming no preset renders anyway; the ladder has no rule
  for choosing `narrow` or `slow`, so none was invented.
- **No candidate.** When no admitted family fits a section at any rung (role and energy,
  energy, role, category), the selector raises `NoEligibleTemplateError`, a
  `ValueError` naming the section, role, energy and candidates. Variety rules still
  relax in their fixed order; the admission never does. Example: a quiet intro (energy
  below 20) when `target_orbit` and `zoom_wave` are both out.
- **Determinism.** Unchanged: seeded SHA-256 tie-break over `seed:section:template`, no
  other randomness, no provider.
- **Experiment.** `AnalysisSnapshot.admission` records the song's admission;
  `HeldConstantIdentity.admission_sha256` binds its hash, so every arm's result echoes
  it and the existing held-constant checks require it equal across arms (it also enters
  the B/C planning-input identity). The runner analyses every song and plans arm A for
  each before any arm runs, so a song arm A cannot plan stops the experiment before any
  planning call or render. A result whose plan names a template outside the admission
  is rejected (`ExperimentBlockedError`).
- **Until C1.2.** Without an admission the selector reads every registered template, as
  before; the snapshot and identity fields are omitted from dumps when None.

## Legacy equality

At the branch point and on this branch, under `PYTHONHASHSEED` 1, 2, 11 and 12, a
script dumped: the candidate set and one-section plan for 14 roles × 16 energies, 300
random songs (1–39 sections, random seeds), 100 reference-arm plans over random admitted
subsets, and an 80-section song. All four dumps are byte-identical (850 entries,
`sha256 0171c86a…00ea`). The existing selector, reference-arm, three-arm and physical
family tests pass unmodified.

## Phase 5 and the experiment protocol (for the owner)

1. Arm A's candidates are the families the gate admits on the experiment's rig for each
   song (six on a zoomless rig), not the 37 old templates.
2. The P2P-T13 spec's "never return nothing" no longer holds: on a physical admission
   arm A can find no family for a section, and the experiment then stops before any
   paid call. With six or seven families, variety constraints relax often; traces
   record each relaxation.
3. Planner intensity, colour, shutter and gobo are still written by every arm (the plan
   schema requires them) but the physical renderer applies none of them, so they no
   longer distinguish arms.
4. `reference_legacy_v1` (`reference_policy.py`, P0-T4) cannot be ported without
   inventing which family is "quiet", "chorus", "entry" and "ending"; the owner chose
   rendered old-renderer files as the Phase 5 legacy reference
   ([viewing render](../2026-11-16-p3-viewing-render/README.md)). Recommended: delete
   it in C1.2 and drop it from Phase 5's creative comparison (`phase-5-evaluation.md`
   line 175), leaving arm A as the deterministic physical reference that D12 asked for.
   The owner decides.
5. The experiment's six preconditions were verified at `8aeda12` against the old
   renderer (`ExperimentPreconditions`). Nobody has re-verified them for the physical
   path.

## What C1.2 deletes

- `deterministic_selector.py`: the `admission is None` branch (registry-wide candidates,
  `load_builtin_templates`, `REGISTRY.list_all()`); `admission` becomes required.
- `deterministic_selector.py` `_build_plan_section`: the reads of `step.color`,
  `step.shutter` and `step.gobo` (C1.3 removes those step fields). On every family they
  read nothing, so a family's section always gets the role's palette colour and no
  events (pinned by
  `test_a_family_yields_the_palette_role_intent_and_no_step_derived_events`); deleting
  them changes no physical plan. Intensity and the palette role stay until T1.
- `three_arm.py`: the None form of `AnalysisSnapshot.admission` and
  `HeldConstantIdentity.admission_sha256`, and the guard around the admitted-template
  check.
- `reference_policy.py` and `test_reference_policy.py`, if the owner accepts item 4.
- Tests that pin old-template selection: `test_deterministic_selector.py` (the
  ten-template candidate list, the legacy intent seam, the always-a-plan matrix that
  includes energies no family covers); the `fan_pulse` plans in
  `test_three_arm_experiment.py` (`_Backend`, `_result`); the 37-entry
  `DeterministicSelector(seed=7)._documents` checks in `test_mh_physical_families.py`.

## Validation

`uv run pytest tests/unit/agents tests/integration tests/unit/reporting/evaluation -q
--no-cov`: 1917 passed, 7 skipped. Ruff check and format on `packages` and `tests`, and
mypy on `packages/twinklr/core/agents` and `packages/twinklr/core/reporting`, clean. No
golden or regression file changed. `make validate` was not run (integrator).
