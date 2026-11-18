---
type: evidence
status: complete
area: engineering
change: 2026_11_12_mh_true_up
created: 2026-11-17
updated: 2026-11-18
---

# W10a — variation variants in the catalog and the gate

**Provenance.** Implemented by an executor agent on 2026-11-17/18 in the worktree
`twinklr-mh-true-up` from `1eca8998`, uncommitted; the integrator commits. Plan:
[w10-arrangement.md](../../plan/w10-arrangement.md) §1 (revised after the critic, with the
integrator's decisions I1–I7). No provider call, no network, no xLights, nothing under
`~/xlights`, `data/` or `artifacts/`; `make validate` not run (the integrator's). Every
value is a proposal; the variants' look has not been viewed (PENDING-OWNER).

## What was built

- **Catalog** (`catalog/templates/moving_heads/*.json`): each of the seven families gains
  six presets after its `narrow` and `slow`: `wide` (every extent `narrow` narrows × 1.5),
  `fast` (every period `slow` doubles, halved; the snap 1 → 0.5 beat) and the four
  combinations `narrow+slow`, `narrow+fast`, `wide+slow`, `wide+fast`, each exactly its
  reach patch then its rate patch (test `test_each_variation_variant_is_its_reach_and_rate_patches`).
- **Off the ladder** (`pipeline.VARIATION_PRESETS`): admission and the effective variant
  read only the ladder (base, `narrow`, `slow`), exactly as before; a family's exclusion
  reasons are its ladder's. Every variation variant is dry-compiled by the gate (critic M9:
  speeds multiply, so no combination is inferred from its parts), offered with its dark
  phases when it passes (`TemplateOffer.variants`), recorded in `preset_exclusions` and
  logged when it fails.
- **Offer-wide data, honest per variant.** Entry dips and `dark_entries` are measured over
  every admitted variant. The overlay exclusions stay over the ladder; a variation
  variant's own beyond them is recorded for it (`TemplateOffer.variant_excluded`), and
  `RigOffer.for_templates(ids, variant)` reads it, as the render's colour resolution now
  does for the preset a section plays. None of the synthetic rigs tried produces such an
  extra exclusion; the merge is unit-tested (`test_a_variation_variant_excludes_its_own_states_only_where_it_plays`).
- Nothing reads `variation` yet (W10c); a section plays a variation variant only by naming
  it in `preset_id`.

## Admission and gate time on the synthetic rigs

`w10a/gate_time.py`, `admit_templates` over the whole catalog (each rig's own families),
wall time on this machine, before (`1eca8998`) and after:

| Rig, tempo, grid | before s | after s | × | variation variants not admitted |
|---|---|---|---|---|
| family rig, 300°/s heads, 129 BPM, 16 bars | 0.95 | 2.50 | 2.6 | cascades `fast`, `wide+fast`; wings `wide+fast` |
| family rig, 300°/s heads, 170 BPM, 16 bars | 0.80 | 1.88 | 2.3 | cascades `fast`, `wide`, `wide+fast`; wings `fast`, `wide+fast`; orbit and snap `wide+fast` |
| family rig, 720°/s, 120 BPM, 16 bars | 0.72 | 2.30 | 3.2 | none |
| tagged family rig, 170 BPM, 16 bars | 1.00 | 3.46 | 3.5 | none |
| zoom rig, 129 BPM, two pickup beats, 16 bars | 1.23 | 3.91 | 3.2 | none |
| owner-like rig, 78.3 BPM, two pickup beats, 62 bars | 5.52 | 17.21 | 3.1 | none |

The admitted families and their effective variants are unchanged on every rig. The gate
costs **2.3–3.5×** (9 variants per family against 3). That is at the critic's "about 3×"
line; proposed, for the integrator to weigh: keep the full grid (the planner can then say
any single step from any source, including a combined one); or drop the four
combinations (5 variants, roughly 1.7×), after which a variation from a source already on
the other axis (a SLOWER section varied WIDEN) cannot be played and is recorded instead.

Where the speed bound predicts it (w10-arrangement §1), the gate agrees: at 300°/s the
cascades' `fast` fails at 129 BPM (bound 127) and `wide` at 170 (bound 170); at 720°/s the
cascades' `wide+fast` fails at 240 BPM (bound 204) where `fast` (306) and `wide` (407)
pass (test `test_every_combined_variant_is_dry_compiled_never_inferred`); at 300°/s and
170 BPM `narrow+fast` is admitted where `fast` is not, and the effective variants stay
on the ladder (test `test_variation_variants_never_decide_admission_or_the_effective_variant`).

## Frames unchanged; fingerprints re-recorded

- **Byte matrix** (`w10a/matrix_fix.py`, the W8 harness, 567 configurations × 23 renders,
  against `1eca8998`'s run): **13,041 of 13,041 renders identical** in frames and `.xsq`.
  The gate record differs in 483 configurations, only in `entry_dips` (the variation
  variants widen the pose envelope a section may be entered from, for example the
  cascades 500 → 560 ms); admitted families, exclusions and effective variants identical.
- **Pins:** every existing pin re-recorded fingerprint only, refusing any moved frame
  (`PINS`, `MULTI_PIN`, `GATED_PIN`, `INTENT_PIN`, `FAST_INTENT_PIN`, `INTENSITY_PINS`,
  `EVENT_PINS`, `TRANSITION_PINS`): frames and `.xsq` unchanged (the template documents
  are render identity, so every fingerprint of a plan using the catalog moves). 84 new
  `PINS`, one per variation variant, family and grid. Golden moving-head fingerprint
  `e509125a…` → `4f2075ad…`.
- **`RENDERER_REVISION` not bumped (12):** no renderer code changes any frame; the only
  output change is for a plan naming a new preset id, which the template documents'
  hash already makes a new render identity. Bump it if the integrator prefers.
- **Planner cache: re-keyed.** Its key hashes the rig offer, which now lists the
  variation variants (and `dark_change_ms`, below): every song plans again once (paid).
  The prompt text itself changes only where `dark_entries` shrink (measured over more
  variants): on the tagged rig at 170 BPM three pairs lose heads, on the owner-like rig
  one (`target_orbit` after `fly_out_cascade`: MH4 no longer always enters dark).

## Tests

`tests/integration/test_mh_families.py`: the catalog lists the nine variants in order;
each variation variant is its patches; combinations dry-compiled (`wide+fast` refused
alone); variation variants never decide admission or the effective variant; `wide`
swings further and `fast` turns over more often than the base on every family, read from
the compiled pan and tilt; the other-meter test now expects every variant admitted.
`tests/unit/.../test_song_intent.py`: the per-variant exclusion merge.
`tests/regression/test_mh_pins.py`: 84 variant pins.

## Verification (this tree, fresh, after the last code edit)

| Command | Result |
|---|---|
| `uv run pytest -q --no-cov` | 7315 passed, 30 skipped (7224 at `1eca8998`) |
| `uv run pytest tests/regression/test_mh_intent_parity.py -q --no-cov` | 26 passed; `--runxfail` 26 passed |
| `uv run ruff check .` | All checks passed |
| `uv run ruff format --check .` | 1308 files already formatted |
| `uv run mypy .` | No issues in 655 source files |

## Look questions (PENDING-OWNER)

1. `wide` (extents × 1.5) and `fast` (period halved): the right amounts?
2. `finite_snap_hold`: its `fast` (0.5 beat) and `slow` (2 beats) barely differ from its
   1-beat base.
3. Gate cost (2.3–3.5×): keep the full grid, or drop the combinations?

Scratch (session-local, not committed):
`/private/tmp/claude-501/-Users-ondeck-work-github-twinklr/9cfb5b66-fff4-47db-adcb-766b50dc61e9/scratchpad/w10a/`
(`gate_time.py`, `gate_before.json`, `gate_after.json`, `matrix_fix.py`,
`matrix_fix.jsonl`, `compare_frames.txt`, `record_variant_pins.py`, `fb.py`, `rvr.txt`).
