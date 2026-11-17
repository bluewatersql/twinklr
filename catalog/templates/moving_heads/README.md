# Moving-head families

Strict JSON `TemplateDoc` documents for the moving-head renderer. They load for every
run (`load_template_catalog`), before any `--template-dir`. The deterministic selector
sees only the families the run's gate admitted, each with its effective variant
(`SelectorAdmission`).

Before planning, the render preflight dry-compiles each family with no preset and with
each preset on the run's rig and song (`admit_templates`). A family is offered
when any of its variants passes there, tried as a ladder: the base (no preset) first,
then its presets in the order it declares them (`narrow`, then `slow`). The first that
passes is the family's **effective variant** on this rig and song: a section naming no
preset renders it, and so does a section naming a preset that was not admitted or that
the family does not declare (with a warning naming why and what plays instead). A
section naming an admitted preset renders that preset. Each variant that fails, the
base included, is logged and recorded in the render trace
(`admission_preset_exclusions`, `preset_id` null for the base), and each effective
variant other than the base is recorded as `admission_effective_presets`. A family none
of whose variants passes is left out of the offer, with every reason, and recorded in
`admission_exclusions`; the run is refused only when no template remains. When the base
passes, the family plays exactly as it did before the ladder. The gate also logs each
admitted family's worst-case section-entry dip, over its admitted variants.

Every family sets explicit start angles and names no rig position preset, authors its
dimmer, and declares `reposition_fallback: drop_accent` on every step, so a
job that sets `moving_heads.reposition_fallback: drop_accent` plays a cue it cannot
reposition into dark. Each declares two variants as presets: `narrow` (less reach) and
`slow` (half the rate). Both ask for less speed than the base, so on a head too slow for
the base at the song's tempo, or a beat too short for the flick's mask, the family
usually still plays through one of them; a variant can also fail where the base plays,
and is then left out on its own. How any family looks is `PENDING-OWNER`; these are
synthetic designs, not accepted looks.

## Meter

The families are authored in 4/4: periods are in beats and cycles in bars, and a 2-bar
4/4 cycle holds whole movement periods (4 beats, `slow` 8) and the flick's overlay
(beats 2 to 6). Each cycle restarts its motion, so in another meter such a cycle would
end mid-path and the head would jump at every cycle boundary. The template compile
therefore grows a repeating cycle that would end mid-period, or before its overlay ends,
with its step, to the smallest whole number of bars that holds them
(`whole_period_cycle`), for the render and the gate alike. Every family then plays in
any meter, its motion running on across each cycle boundary; in 4/4 nothing changes.
What the meter still changes is how many bars a cycle spans (`base`/`narrow`, then
`slow`):

| Meter | Cascades, orbit, wings, zoom wave | Flick | Snap |
|---|---|---|---|
| 4/4 | 2, 2 bars | 2, 2 bars | 1 bar, `ONCE` |
| 2/4 | 2, 4 bars | 4, 4 bars (8 beats, to hold the overlay) | 1 bar |
| 3/4, 5/4, 7/8 | 4, 8 bars | 4, 8 bars | 1 bar |
| 6/8 (six beats a bar) | 2, 4 bars | 2, 4 bars | 1 bar |

The flick's overlay plays once per cycle, at beats 2 to 6: every 8 beats in 4/4 and 2/4,
every 12 in 3/4 and 6/8 (24 under `slow`). A section shorter than a cycle plays
the cycle's head, as in 4/4. A cycle is never grown past 8 bars: a template whose
periods meet whole bars only later is refused, naming the cycle it would need (no
shipped family needs more than 8 bars in any meter). A cycle whose steps
do not each span it is left as authored, since its motion restarts at each step by
design.

Each cycle starts on the 20 ms frame nearest its downbeat, so where bars sit at
varying distances from the frame grid (any detected tempo that drifts), a cycle
restarting its phase at its own frame would leave the pose a few hundredths of a degree
off where the previous cycle ended: a jump with no time to travel, which a head near
its speed limit cannot play. A step's cycles that follow one another without a gap
therefore continue one musical phase from the first, and meet at the same pose. On a
grid whose bars all sit at one distance from the frame grid nothing changes.

This is renderer revision 2. Revision 1 cut a non-4/4 cycle mid-period, which
left the orbit, the wings and the zoom wave out in 3/4 and the `slow` variants out in
6/8 and played a cascade's 1.5 periods per 3/4 cycle, and it restarted each cycle at
its own frame, which on a drifting grid left heads near their limit out (on the owner's
rig, the wings' `narrow` variant).

## Head speed

The variants are only narrower or slower, so a head too slow for every one of them
loses the family. Measured on 2026-11-16 on four heads (20 ms latency, 60 ms settle,
150 ms wheels) over a minute of beats jittered by 8%, alike in 4/4 and 3/4:

- At 150°/s every family but the zoom wave plays from 50 to 180 BPM; at 200 BPM all but
  the flick.
- The cascades need 100°/s at 150 BPM, 120°/s at 180 BPM and 130°/s at 200 BPM, each
  through `slow` (measured in steps of 5°/s).
- The flick needs 95°/s at 180 BPM in 4/4 and 110°/s in 3/4, and plays at no speed at
  200 BPM, where one beat is shorter than its mask needs.
- The wings, the orbit and the snap play down to 90°/s up to 180 BPM; at 200 BPM the
  wings need 100°/s, below which only the snap and the orbit remain.
- Every family plays at 50 BPM down to 90°/s.

No declared variant is slower than `slow` at full reach, so nothing below that plays.

## Families and what each needs

Every family needs pan and tilt axes whose `travel_speed_per_s`, `latency_ms` and
`settle_ms` are declared, and each pose below inside the axis limits. Speeds are the
base's peak at 120 BPM; they scale with tempo (1.5 times at 180 BPM), and where the
base is faster than the profile declares the gate tries the family's variants. Repeats
are as authored in 4/4 (see Meter for other meters).

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
Its zoom waves on the sway's own phase (`zoom`, `sine`), so it lags with each
head's place in the wave. `narrow` narrows only the sway (a preset cannot patch the zoom),
and `slow` halves the rate of both. On a rig with a zoom axis every other family holds
the zoom at the profile's default byte, and between sections the zoom moves only in the
dark and settles before the reveal, like pan and tilt.

It was designed and checked only against a synthetic profile:
`zoom_pilot_profile_payload` in `tests/support/moving_heads.py`, laid out for a
16-channel DMX model with every offset in 1-16 (16-bit pan 1/2 and tilt 3/4, dimmer 5,
shutter 6, color 7, gobo 8, an 8-bit zoom on 9 whose 10°-40° beam angle maps over bytes
20-220 at 90°/s with 40 ms settle). That layout is prepared for validation against an
owner's fixture; none of its values is a real fixture's, and accepting a real profile,
and how the family looks, is `PENDING-OWNER`.

## Worst-case entry dips (synthetic, 8 heads)

Measured on 2026-11-16 with the six families on the 8-head synthetic rig: the dip is the
longest a head may stay dark entering a section of the family, from any pose and wheel
state an admitted variant of any family or the initial state leaves. Admitting more
families or variants widens that envelope, so another family's dip can grow, and a
variant entering on a wheel state with no known settle time can lose its bound and not
be admitted (a family with no variant left is left out; a `--template-dir` template
then refuses the run). Whether these look acceptable is `PENDING-OWNER`.

| Profile | 60–120 BPM | 150 BPM | 180 BPM |
|---|---|---|---|
| synthetic, 720°/s, 40 ms settle | 300–340 ms, 1 beat | 1 beat | 1–2 beats |
| 360°/s, 40 ms settle | 380–460 ms, 1 beat | 1–2 beats | 2 beats |
| 180°/s, 20 ms latency, 100 ms settle, 300 ms wheels | 600–1020 ms, 1–2 beats | 2 beats | 2 beats |

On the 180°/s profile `masked_wheel_flick` is left out from 120 BPM (its one-beat mask
is shorter than the 540 ms its wheel change needs), and `fly_out_cascade`,
`fly_in_cascade` and `mirror_wings` at 180 BPM (motion faster than the profile). Those
exclusions were measured before the variant ladder; a family is now left out only where
its `narrow` and `slow` variants fail too.

Those rows predate `zoom_wave`, which a zoomless rig leaves out. Measured on 2026-11-16
on the 8-head zoom pilot rig with all seven families admitted: 500 ms, and 520 ms for
`masked_wheel_flick`, longer than on a zoomless rig because the zoom's travel (up to 25°
at 90°/s) is the longest travel term; that is 1 beat at 120 BPM (2 for the flick) and 2
beats where the shortest beat is 380 ms.
