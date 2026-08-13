# Golden render harness (P1P-T1)

This suite makes the render output *visible* to CI. Before it existed, no test anywhere
asserted the content of a generated settings string, an `E_VALUECURVE_DMX` payload, or a
byte of `.xsq`, and the only end-to-end render test patched `compile_template` with a
`MagicMock` — so the compiler, handlers, curves and exporter never ran under test.

## What is pinned

| File | Behavior pinned |
|---|---|
| `test_settings_golden.py` | The complete emitted settings string of every effect, per rig, against a committed golden |
| `test_shutter_channel_emission.py` | `shutter_channel=6` → `E_SLIDER_DMX6=0` emitted; `shutter_channel=17` → no `E_SLIDER_DMX17` token |
| `test_xsq_round_trip.py` | `parse → export → parse` over the repo's first tracked `.xsq` |
| `test_validator_on_golden_render.py` | The existing 587-LOC validator runs against a freshly rendered sequence |
| `test_blackout_full_brightness.py` (P1P-T2) | P4-M2: `pop_lock_spotlight_blackout` under `energetic` emits `E_SLIDER_DMX15=255` instead of 0 |
| `test_dimmer_floor_dropped.py` (P1P-T2) | P4-M1: `circle_asym_left_strobe`'s dimmer curve dips below the template's declared 60-DMX floor |
| `test_8head_role_mismatch.py` (P1P-T2) | P4-F26 (stronger than "degraded ordering"): the 8-head rig renders zero section segments — every fixture's positional role (`ALL_0..ALL_7`) misses every template's declared role names |

Rigs live in `harness.py` (`RIGS`); goldens live in `<rig_id>/<section_id>.settings.txt`.

## The goldens encode broken output on purpose

The render path has known defects at this baseline. The goldens capture them so each
Lane-R fix in P1P-T3..T6 arrives as a reviewable diff instead of unexplained churn.
Every known-wrong pin carries a `KNOWN-WRONG PIN` comment naming its defect id; the
banner at the top of each golden file lists what is visible in the baseline. **Do not
read a golden as a statement of desired output.**

When a Lane-R fix lands, the corresponding test fails by design. Read the diff, confirm
it is the intended behavioral change, update the affected `KNOWN-WRONG PIN` assertion,
and regenerate.

## Regenerating

```bash
uv run pytest tests/golden --regen-goldens -q
# equivalently:
TWINKLR_REGEN_GOLDENS=1 uv run pytest tests/golden -q
git diff --stat        # the behavioral change, as a diff
```

A normal run never writes goldens: `uv run pytest tests/golden -q` twice in a row must
leave `git status --porcelain` empty.

## Extending (P1P-T2)

`harness.py` owns the minimal deterministic rig and plan fixtures the golden tests need,
authored here because P1P-T1 lands before P1P-T2. T2 is expected to **extend** `RIGS`
and `build_plan()` rather than replace the harness. Adding a rig or a section requires a
regeneration pass; `test_every_rendered_section_has_a_golden` fails if a newly emitted
section has no committed pin.

P1P-T2 added:
- `RIGS["mh8_reference"]` — an 8-fixture rig, added to prove the pipeline is not
  4-specific. It instead surfaced a **stronger** version of P4-F26: an 8-fixture group
  gets positional roles (`ALL_0..ALL_7`, `fixture_builder.py`'s `_ROLE_MAPS` only covers
  1-4), which match none of the role names every builtin template declares, so
  `compile_template` silently skips every section for this rig — only the (also
  defective) transition segments render. See `test_8head_role_mismatch.py`.
- Two `build_plan()` sections, `drop` (`pop_lock_spotlight_blackout`, `energetic`) and
  `breakdown` (`circle_asym_left_strobe`, `chill`), so P4-M1 (dropped dimmer floor) and
  P4-M2 (BLACKOUT full-brightness inversion) are visible pinned golden behavior rather
  than latent bugs with no golden coverage. See `test_blackout_full_brightness.py` and
  `test_dimmer_floor_dropped.py`.

## Determinism

`test_golden_render_is_deterministic` renders each rig twice and compares. The inputs are
fixed (120 bpm, 8 bars, fixed template and preset ids, no LLM calls, no clock, no
randomness) and effects are sorted before serialization, so goldens never depend on dict
ordering. `n_samples` is not settable through `RenderingPipeline`, so
`test_golden_harness_pins_n_samples` asserts the default the goldens were generated at.
