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
| `test_delivery_artifacts.py` (P1P-T11) | What a real render hands the user: the fresh `.xsq` re-parses through `XSQParser` and names only Twinklr's models, the `.xtiming` markers equal the `.xsq` timing tracks, and the `.xmap` names what was emitted |
| `test_xlights_acceptance.py` (P1P-T12, **LOCAL-ONLY**, `requires_xlights`) | Whether a real xLights 2026.15 accepts what Twinklr emits — import with/without `xlights_rgbeffects.xml`, version-stamp acceptance, `.xtiming` standalone import, shutter-open output on the >16-channel rig, and the `split_lr_sweep_counter` overlap-clamp probe. See "xLights acceptance (P1P-T12)" below |

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

## xLights acceptance (P1P-T12)

`test_xlights_acceptance.py` is a **LOCAL-ONLY** regression suite (`requires_xlights`
marker, `tests/golden/conftest.py`) that drives a real, running xLights 2026.15 over
its unauthenticated HTTP automation API
(`tests/golden/xlights_client.py`, default `http://127.0.0.1:49913`) to pin the
answers to the four questions
`build/specs/phase-1p-render-truth/P1P-T12-xlights-acceptance-test.md` posed. It
never runs in CI: `pytest_collection_modifyitems` probes the API once at collection
time and skips every `requires_xlights` test with an explicit reason when nothing
answers — exactly what happened on every run to date.

### Run record

| Date | Twinklr SHA | xLights build | API reachable | Rigs | Result |
|---|---|---|---|---|---|
| 2026-08-14 | `2e77f9d7c093ba364257de79cc8ca89277b59bc5` | N/A — xLights not installed on the executing machine | **No** (`127.0.0.1:49913` and `:49914` both refused connections) | `mh4_minimal`, `mh4_shutter_out_of_window` | All 7 tests **SKIPPED** (collection-time, `requires_xlights`). No empirical evidence gathered this run. |

**Q1–Q4 status: UNANSWERED as of the above run.** The owner's 2026-08-14 empirical
note in the spec (bare `.xsq` imports without `xlights_rgbeffects.xml`) stands as the
project's authoritative answer to Q1; this suite exists to keep re-confirming it
against future xLights versions, and has not yet had the chance to run against a real
instance. Nothing in this run's evidence contradicts or confirms it beyond what the
spec already records.

**Ground-truth fixture: not yet committed.** The spec's protocol calls for saving the
imported sequence from xLights and committing the diff against the generated file as
the repository's first ground-truth fixture. That step requires a live xLights
session to produce and could not be performed this run — filed as the immediate
follow-up (see below), not fabricated.

**Effect-parameter UI inspection (P5 §V4 risk 5 — silently-ignored `E_*` keys):**
not scriptable through the documented automation surface (M6b lists no
"get effect parameters" command); this remains a manual step for whoever runs this
suite against a live xLights, alongside the automated assertions.

### To actually run this suite

1. Launch xLights 2026.15, open (or create) a show directory, and enable the HTTP
   automation API in Tools → Preferences (local interface only). The suite itself
   calls `newSequence` before every test (an `autouse` fixture in the test module),
   so each import lands in a fresh, throwaway sequence rather than whatever you had
   open — you do not need to create one yourself, but you do need xLights running
   against *a* show directory first.
2. **Nothing saves automatically.** `importXLightsSequence` targets that throwaway
   sequence; close xLights (or the sequence) **without saving** after each run
   unless you are deliberately doing step 4 below. The client deliberately has no
   `save` wrapper — see `xlights_client.py`'s docstring for why.
3. For the two Q1 arms specifically, run the suite **twice**, setting
   `TWINKLR_XLIGHTS_SHOWDIR_MODE` to say which show directory is open — the API has
   no documented "open show directory" command, so this is an operator precondition
   the env var makes explicit rather than implicit. The mismatched arm skips with a
   reason naming the required mode instead of silently passing:
   ```bash
   # xLights open against a show directory that HAS xlights_rgbeffects.xml:
   TWINKLR_XLIGHTS_SHOWDIR_MODE=with_rgbeffects uv run pytest tests/golden/test_xlights_acceptance.py -v
   # xLights open against a show directory that LACKS it:
   TWINKLR_XLIGHTS_SHOWDIR_MODE=bare uv run pytest tests/golden/test_xlights_acceptance.py -v
   ```
   Everything else in the module runs under either invocation (the env var only
   gates the two Q1 tests).
4. In the xLights UI: inspect one imported effect's parameters against the emitted
   settings string (spec risk 5), save the sequence, and diff the saved file against
   the generated one (`xmllint --format` both sides). Commit the saved file plus a
   diff summary as the ground-truth fixture, and update the run record above.
5. Disable the automation API again — it is unauthenticated (M6b).

### Follow-up filed

Producing the xLights-saved ground-truth fixture (spec's step 9/10, and the
`test_emitted_xsq_matches_saved_ground_truth_structure` CI assertion it would enable)
needs a machine with xLights 2026.15 installed and available for interactive use.
Route to the owner or a follow-up task rather than fabricated here.
