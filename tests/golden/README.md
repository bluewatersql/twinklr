# Golden render harness (P1P-T1)

This suite makes the render output *visible* to CI. Before it existed, no test anywhere
asserted the content of a generated settings string, an `E_VALUECURVE_DMX` payload, or a
byte of `.xsq`, and the only end-to-end render test patched `compile_template` with a
`MagicMock` — so the compiler, handlers, curves and exporter never ran under test.

## What is pinned

| File | Behavior pinned |
|---|---|
| `test_settings_golden.py` | The complete emitted settings string of every effect, per rig, against a committed golden; plus the transition blend, the value-curve channel ordering, and the two remaining known-wrong pins below |
| `test_shutter_channel_emission.py` | `shutter_channel=6` → `E_SLIDER_DMX6=0` emitted; `shutter_channel=17` → no `E_SLIDER_DMX17` token |
| `test_xsq_round_trip.py` | `parse → export → parse` over the repo's first tracked `.xsq` |
| `test_validator_on_golden_render.py` | The existing 587-LOC validator runs against a freshly rendered sequence |
| `test_blackout_is_black.py` (T2 → flipped in T5) | P4-M2 repaired: both blackout templates emit `E_SLIDER_DMX15=0` under all four presets. Was `test_blackout_full_brightness.py`, pinning the 255 inversion |
| `test_dimmer_floor_honored.py` (T2 → flipped in T5) | P4-M1 repaired: no non-blackout dimmer curve dips below the template's declared 60-DMX floor; the blackout's exemption is explicit. Was `test_dimmer_floor_dropped.py` |
| `test_8head_rig_renders.py` (T2 → flipped in T5) | P4-F26 repaired: the 8-head rig renders every plan section on all eight heads, roles are spatial, and a group the rig cannot fill raises `UnsupportedRigShapeError`. Was `test_8head_role_mismatch.py` |
| `test_calibrated_movement_range.py` (P1P-T5) | P4-F9: every emitted pan/tilt value stays inside the rig's calibrated window, and a narrow window really does narrow the output |

Rigs live in `harness.py` (`RIGS`); goldens live in `<rig_id>/<section_id>.settings.txt`.

## The goldens still encode some broken output on purpose

Two defects remain visible in the committed goldens, both owned by **P1P-T6**:

- **P4-F3** — every channel 1..16 is emitted, unchoreographed ones zero-filled, so
  `E_SLIDER_DMX<n>=0` means "zero-filled", not "commanded to 0"
  (`test_unchoreographed_channels_are_zero_filled`).
- **P4-F10** — value-curve points are written at 2-decimal resolution
  (`test_value_curve_points_are_two_decimal`).

Each carries a `KNOWN-WRONG PIN` comment naming its defect id, and the banner at the top
of every golden file lists both, alongside the P1P-T5 repairs the goldens now encode as
*correct* behavior. **Do not read a `KNOWN-WRONG PIN` as a statement of desired output.**

When a Lane-R fix lands, the corresponding test fails by design. Read the diff, confirm
it is the intended behavioral change, flip the affected pin (rename the file if its name
now describes the defect rather than the behavior), and regenerate.

## Regenerating

```bash
uv run pytest tests/golden --regen-goldens -q
# equivalently:
TWINKLR_REGEN_GOLDENS=1 uv run pytest tests/golden -q
git diff --stat        # the behavioral change, as a diff
```

A normal run never writes goldens: `uv run pytest tests/golden -q` twice in a row must
leave `git status --porcelain` empty.

Every hunk of a regeneration must be attributable to a named fix. The five categories the
P1P-T5 regeneration produced, as a worked example of what "attributable" means:

1. **Movement value-curve ranges** (`E_VALUECURVE_DMX11`/`13`, all four plan sections) —
   P4-F9. The new ranges match the rig's calibrated windows exactly.
2. **`E_SLIDER_DMX15` 255 → 0 in `drop`** — P4-M2.
3. **`chorus` dimmer curve minima** — P4-M1 alone: the floor maps `v` onto
   `[60, 255]`, so `0.51 → 0.63` is exactly `(60 + 0.51 x 195) / 255`.
4. **`breakdown` dimmer curve** — P4-M1 **and** P4-F8 together, not M1 alone. The section
   renders under `chill` → `Intensity.SLOW`, which had no `DEFAULT_DIMMER_PARAMS` entry
   and silently fell back to SMOOTH; the new SLOW entry drops `max_intensity` from 128 to
   100, which scales the curve *before* the floor maps it. Applying only the floor
   arithmetic to the old values does not reproduce the new ones — that mismatch is the
   signal that a second fix is in the hunk.
5. **Value curves appearing in transition sections** — the settings builder now reads
   `ChannelValue.curve`, so the blend reaches the exporter instead of being dropped.

## Extending

`harness.py` owns the deterministic rig and plan fixtures the golden tests need. Later
tasks **extend** `RIGS` and `build_plan()` rather than replace the harness. Adding a rig
or a section requires a regeneration pass; `test_every_rendered_section_has_a_golden`
fails if a newly emitted section has no committed pin.

P1P-T2 added:
- `RIGS["mh8_reference"]` — an 8-fixture rig, added to prove the pipeline is not
  4-specific. It instead surfaced a stronger version of P4-F26: the rig rendered *no*
  section segments at all. P1P-T5 fixed it, and `mh8_reference` now has full section
  goldens rather than transitions-only ones.
- Two `build_plan()` sections, `drop` (`pop_lock_spotlight_blackout`, `energetic`) and
  `breakdown` (`circle_asym_left_strobe`, `chill`), so P4-M1 and P4-M2 had golden
  coverage before P1P-T5 repaired them.

P1P-T5 added:
- `RIGS["mh4_narrow_calibration"]` — 4 heads calibrated to `tilt 110-145, pan 100-150`,
  the P4-F9 worked example. Every other rig uses the default movement limits, which are
  wide enough that a curve escaping them is easy to overlook.
- Three `build_plan()` sections (and the three transitions between them), extending the
  plan from 16 to 32 bars: `one_bar` (bar 17, `sweep_lr_fan_hold`) pins that a section
  shorter than the template's cycle renders the truncated *head* of that cycle where it
  used to render nothing at all; `phrase` (bars 18-25, `intro_main_outro_phrase`) and
  `arc` (bars 26-31, `build_drop_recover`) pin that narrative templates play every step
  they declare, so their FADE_IN entries and FADE_OUT exits reach the output.

## Determinism

`test_golden_render_is_deterministic` renders each rig twice and compares. The inputs are
fixed (120 bpm, 32 bars, fixed template and preset ids, no LLM calls, no clock, no
randomness) and effects are sorted before serialization.

In-process repetition is not sufficient on its own: the transition compiler collected its
channels into a `set[ChannelName]`, which iterates in hash order, so the emitted string
differed *between processes* while matching itself within one. That was invisible until
the blend started reaching the exporter at all. Both ends are now ordered — insertion
order in `transition_segment_compiler`, ascending channel order in the settings builder —
and `test_value_curves_are_emitted_in_channel_order` pins it. When touching the emit
loop, re-run the suite under a few values of `PYTHONHASHSEED`.

`n_samples` is not settable through `RenderingPipeline`, so
`test_golden_harness_pins_n_samples` asserts the default the goldens were generated at.
