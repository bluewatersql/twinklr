# Physical moving-head families

Strict JSON `TemplateDoc` documents for the opt-in `physical_v2` renderer. They load only
for a `physical_v2` job (`admit_physical_catalog`), after the Python builtins and before
any `--template-dir`; a legacy run, the deterministic selector and the 37-entry builtin
registry never see them. They live outside `catalog/templates/moving_heads`, whose
documents must stay model-equal to their Python builtins.

Before planning, the render preflight dry-compiles each family with no preset and with
each preset on the run's rig and song (`check_physical_templates`). A family whose base
(no preset) fails there is left out of the planner's offer with its presets, and the
reason is logged and recorded in the render trace (`admission_exclusions`); the run is
refused only when no template remains. A family whose base passes is offered, and only
a preset that fails is left out, logged and recorded (`admission_preset_exclusions`); a
section naming it renders the family without a preset, as for a preset the family does
not declare. The gate also logs each admitted family's worst-case section-entry dip.

Every family sets explicit start angles and names no rig position preset, authors its
dimmer, and declares `physical_reposition_fallback: drop_accent` on every step, so a
job that sets `moving_heads.reposition_fallback: drop_accent` plays a cue it cannot
reposition into dark. Each declares two variants as presets: `narrow` (less reach) and
`slow` (half the rate). Both ask for less speed than the base, but a variant can still
fail where the base plays (see Meter), and the gate checks the base and both variants:
a failing variant is left out on its own, a failing base leaves the whole family out.
How any family looks is `PENDING-OWNER`; these are synthetic designs, not accepted
looks.

## Meter

The families are authored for 4/4. Periods are in beats and cycles in bars, so the
continuous families' 2-bar cycles span whole movement periods only when a bar has four
beats. Measured on a 4-head rig at 500 ms beats:

- 3/4: a 2-bar cycle is 6 beats, which ends `target_orbit`, `mirror_wings` and
  `zoom_wave` (period 4 beats, `slow` 8) mid-path, so the head would jump at every cycle
  boundary; all three are left out. The cascades, the snap and the flick play, but differently: a cascade's
  cycle holds 1.5 periods, so a head lights one or two strokes per cycle depending on
  its stagger; the flick's sway reverses direction at each cycle boundary, and its flick
  spans beats 2 to 6 of a 6-beat cycle.
- 6/8 (six beats a bar): the base periods fit, but the `slow` variants of
  `target_orbit`, `mirror_wings` and `zoom_wave` (8 beats in a 12-beat cycle) do not, so
  those families are offered with `narrow` only; the others play with both variants.

## Families and what each needs

Every family needs pan and tilt axes whose `travel_speed_per_s`, `latency_ms` and
`settle_ms` are declared, and each pose below inside the axis limits. Speeds are the
base's peak at 120 BPM; they scale with tempo (1.5 times at 180 BPM), and the gate
refuses a family whose motion is faster than the profile declares.

| Family | Motion and light | Repeat | Rig presets | Topology | Other capabilities | Peak speed at 120 BPM |
|---|---|---|---|---|---|---|
| `fly_out_cascade` | Periodic pan sweep of ±45° about pan 0°, tilt 30°, mirrored by wing; lit only while each head travels from the centre out to its wing's edge (movement phase 0.25 to 0.5), dark for the return; heads staggered over a quarter period | `JOINER`, 2 bars, period 4 beats | none | required (declared, or derived from `position.position_index`) | a shutter declaring `open_state` (the envelope opens it) | pan 141°/s |
| `fly_in_cascade` | As `fly_out_cascade`, lit from the edge in to the centre (phase 0.5 to 0.75) | as above | none | required | as above | pan 141°/s |
| `target_orbit` | Every head circles pan 0°, tilt 30° (±25° pan, ±15° tilt) together, lit throughout, one revolution every four beats | `JOINER`, 2 bars, period 4 beats | none | not needed | a dimmer axis; a shutter state named `open` | pan 79°/s, tilt 47°/s |
| `mirror_wings` | Mirrored figure-eights (lissajous 1:2, ±35° pan, ±15° tilt) about pan 0°, tilt 30°, lit throughout, in a wave from the centre out | `JOINER`, 2 bars, period 4 beats | none | required | a dimmer axis; a shutter state named `open` | pan 110°/s, tilt 94°/s |
| `finite_snap_hold` | Tilts from 10° to 55° in one beat, then holds that pose lit to the section end; one move per section | `ONCE`, 1 bar, `HOLD_LAST_POSE` | none | not needed | a dimmer axis; a shutter state named `open` | tilt 90°/s |
| `zoom_wave` | Every head sways pan ±15° about pan 0°, tilt 30°, lit throughout, while its beam angle waves 15° to 35° (±10° about 25°) with the sway, widest a quarter period in; heads staggered over a quarter period, in a wave across the rig | `JOINER`, 2 bars, period 4 beats | none | required | a dimmer axis; a shutter state named `open`; a `zoom` axis admitting 15° to 35° whose `travel_speed_per_s`, `latency_ms` and `settle_ms` are declared, and an initial `zoom_deg` | pan 47°/s, zoom 31°/s |
| `masked_wheel_flick` | Sways pan ±20° about pan 0°, tilt 30°, lit; over beats 2 to 6 of each 8-beat cycle the color wheel turns to the rig's `flick` state, masked dark for one beat while it turns each way, then back to the base color | `JOINER`, 2 bars, period 4 beats | attribute preset `flick` setting `color` for every head (its fallback chain may supply it) | not needed | a dimmer axis; a shutter state named `open`; a color wheel whose change, with the head's travel and settle, fits in one beat | pan 63°/s |

Without a topology `fly_out_cascade`, `fly_in_cascade`, `mirror_wings` and `zoom_wave`
are left out; without the `flick` attribute preset `masked_wheel_flick` is; without a
`zoom` axis on every head `zoom_wave` is (its zoom is not optional). `target_orbit`,
`mirror_wings`, `finite_snap_hold`, `masked_wheel_flick` and `zoom_wave` hold the shutter
in the state named `open`: the profile must declare a shutter state with exactly that name, or they
are left out with the missing state in the reason (the cascades use the profile's
`open_state`, whatever it is named). A head on the axis of an odd-sized rig's mirror
(pan sign 0) does not move in pan under the mirrored families.

The cascades, the wings and the zoom wave take each head's phase from its place in the
rig topology.
A declared `topology` keeps every head's rank when a head is missing. A topology derived
from `position.position_index` cannot see a missing head after the highest remaining
index, so removing the highest-index head shortens the row and can change the other
heads' phases; declare a topology to keep them.

## Zoom pilot (synthetic)

`zoom_wave` is the bounded optical pilot (P2.5): one continuous optical axis, the zoom's
beam angle, through the same physical encoding and dark repositioning as pan and tilt.
Its zoom waves on the sway's own phase (`physical_zoom`, `sine`), so it lags with each
head's place in the wave. `narrow` narrows only the sway (a preset cannot patch the zoom),
and `slow` halves the rate of both. On a rig with a zoom axis every other family holds
the zoom at the profile's default byte, and between sections the zoom moves only in the
dark and settles before the reveal, like pan and tilt.

It was designed and checked only against a synthetic profile:
`zoom_pilot_profile_payload` in `tests/support/mh_physical.py`, laid out for a
16-channel DMX model with every offset in 1-16 (16-bit pan 1/2 and tilt 3/4, dimmer 5,
shutter 6, color 7, gobo 8, an 8-bit zoom on 9 whose 10°-40° beam angle maps over bytes
20-220 at 90°/s with 40 ms settle). That layout is prepared for validation against an
owner's fixture; none of its values is a real fixture's, and accepting a real profile,
and how the family looks, is `PENDING-OWNER`.

## Worst-case entry dips (synthetic, 8 heads)

Measured on 2026-11-16 with the six families on the 8-head synthetic rig: the dip is the
longest a head may stay dark entering a section of the family, from any pose and wheel
state an admitted family or the initial state leaves. Admitting more families or presets
widens that envelope, so another family's dip can grow, and a template entering on a
wheel state with no known settle time can lose its bound and be left out (a
`--template-dir` template then refuses the run). Whether these look acceptable is
`PENDING-OWNER`.

| Profile | 60–120 BPM | 150 BPM | 180 BPM |
|---|---|---|---|
| synthetic, 720°/s, 40 ms settle | 300–340 ms, 1 beat | 1 beat | 1–2 beats |
| 360°/s, 40 ms settle | 380–460 ms, 1 beat | 1–2 beats | 2 beats |
| 180°/s, 20 ms latency, 100 ms settle, 300 ms wheels | 600–1020 ms, 1–2 beats | 2 beats | 2 beats |

On the 180°/s profile `masked_wheel_flick` is left out from 120 BPM (its one-beat mask
is shorter than the 540 ms its wheel change needs), and `fly_out_cascade`,
`fly_in_cascade` and `mirror_wings` at 180 BPM (motion faster than the profile).

Those rows predate `zoom_wave`, which a zoomless rig leaves out. Measured on 2026-11-16
on the 8-head zoom pilot rig with all seven families admitted: 500 ms, and 520 ms for
`masked_wheel_flick`, longer than on a zoomless rig because the zoom's travel (up to 25°
at 90°/s) is the longest travel term; that is 1 beat at 120 BPM (2 for the flick) and 2
beats where the shortest beat is 380 ms.
