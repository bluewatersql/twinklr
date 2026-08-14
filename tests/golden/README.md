# Golden render harness (P1P-T1)

This suite makes the render output *visible* to CI. Before it existed, no test anywhere
asserted the content of a generated settings string, an `E_VALUECURVE_DMX` payload, or a
byte of `.xsq`, and the only end-to-end render test patched `compile_template` with a
`MagicMock` — so the compiler, handlers, curves and exporter never ran under test.

## What is pinned

| File | Behavior pinned |
|---|---|
| `test_settings_golden.py` | The complete emitted settings string of every effect, per rig, against a committed golden; plus the transition blend and the value-curve channel ordering |
| `test_shutter_channel_emission.py` | `shutter_channel=6` → `E_SLIDER_DMX6=255` (declared default); `shutter_channel=17` → `E_SLIDER_DMX17=255` (the window now reaches it too) |
| `test_xsq_round_trip.py` | `parse → export → parse` over the repo's first tracked `.xsq` |
| `test_validator_on_golden_render.py` | The existing 587-LOC validator runs against a freshly rendered sequence, including its shutter/colour/gobo channel-map cross-check |
| `test_blackout_is_black.py` (T2 → flipped in T5) | P4-M2 repaired: both blackout templates emit `E_SLIDER_DMX15=0` under all four presets. Was `test_blackout_full_brightness.py`, pinning the 255 inversion |
| `test_dimmer_floor_honored.py` (T2 → flipped in T5) | P4-M1 repaired: no non-blackout dimmer curve dips below the template's declared 60-DMX floor; the blackout's exemption is explicit. Was `test_dimmer_floor_dropped.py` |
| `test_8head_rig_renders.py` (T2 → flipped in T5) | P4-F26 repaired: the 8-head rig renders every plan section on all eight heads, roles are spatial, and a group the rig cannot fill raises `UnsupportedRigShapeError`. Was `test_8head_role_mismatch.py` |
| `test_calibrated_movement_range.py` (P1P-T5) | P4-F9: every emitted pan/tilt value stays inside the rig's calibrated window, and a narrow window really does narrow the output |

Rigs live in `harness.py` (`RIGS`); goldens live in `<rig_id>/<section_id>.settings.txt`.

## No known-broken output remains (as of P1P-T6)

P1P-T6 repaired the last two defects the goldens deliberately encoded:

- **P4-F3** — an unwritten channel the fixture *maps* now emits its declared default
  (`shutter_default=255`, or the color/gobo map's `"open"` entry) instead of a
  zero-fill; a channel the fixture does not map is omitted from the settings string
  entirely; the emitted window comes from `get_max_channel`, not a floor-16 guess.
  Was `test_unchoreographed_channels_are_zero_filled`, now
  `test_unmapped_channels_are_omitted_not_zero_filled`.
- **P4-F10** — value-curve points are written at 4-decimal resolution. Was
  `test_value_curve_points_are_two_decimal`, now `test_value_curve_points_are_four_decimal`.

The banner at the top of every golden file records both as repaired. When a future
Lane-R-shaped fix lands, its corresponding test fails by design: read the diff, confirm
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

The P1P-T6 regeneration is two categories, both present in every golden file:

1. **Emitted `E_SLIDER_DMX`/`E_CHECKBOX_INVDMX` window** — P4-F3. The window is now
   `get_max_channel`, not floor-16/round-to-16: `mh4_minimal` (pan/tilt/dimmer only)
   shrinks from 16 to 15, dropping channels 1-10/12/14/16 entirely rather than
   zero-filling them; `mh4_shutter_in_window` gains `E_SLIDER_DMX6=255` (declared
   shutter default) where it used to hold `=0`; `mh4_shutter_out_of_window` gains
   `E_SLIDER_DMX17=255` and `E_SLIDER_DMX18=0` (declared shutter/colour defaults),
   both previously absent because 17/18 fell outside the old window.
2. **Value-curve point precision** (every `E_VALUECURVE_DMX` payload) — P4-F10. Points
   are now `t:v` at 4 decimals instead of 2; the underlying curve values are unchanged,
   only their written precision is, so a curve's *shape* in the diff is identical, not
   its digit count. The signal that no third fix is hiding in a hunk: subtracting the
   window/default changes above and re-rounding the remaining `E_VALUECURVE_DMX` values
   to 2 decimals reproduces the pre-T6 file exactly.

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
