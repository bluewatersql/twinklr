---
type: plan
status: active
area: product
change: 2026_11_12_mh_true_up
created: 2026-11-18
updated: 2026-11-18
---

# Owner decisions pending — moving-head true-up

This list collects every open PENDING-OWNER look question and every reversible integrator
decision from the W1–W10 records. Answer an item by replying with its number. Until the
owner answers, the build keeps doing what the "Today" column says.

The renders to watch are owner-rig renders of the owner's song (see the
[handoff](handoff.md#how-to-validate-and-review) for how they are made). Their videos are
local, in the owner's folder `~/xlights/_twinklr_verify/p4_view/out/`, and are never copied
into the repository. In the "See" column, "video" means the file prefix given below the
group's heading.

## Intensity (W5)

Video prefix: `intensity_*` (A as built, and B the headroom variant).

| # | Question | Today | See | If answered the other way |
|---|---|---|---|---|
| I1 | **Full-level families: A (dip-and-return) or B (the headroom variant)?** The integrator recommends **B** | A. A full family sags from full and returns to full on each accent (INTENSE to 60% every beat, DRAMATIC to 75% every half bar) | [W5](../evidence/2026-11-17-w5-intensity/README.md#the-table-proposed-for-the-owners-view); the B patch and its levels are in the [W6/W7 record](../evidence/2026-11-17-w6-w7-events/README.md), "H2 headroom variant"; video (A against B) | B: families are authored at 0.82 and accents rise above that, so the light gets brighter on the beat instead of dipping. Changes `intensity.py`, re-pins frames, bumps the revision |
| I2 | INTENSE dip depth (0.40) and DRAMATIC floor and period (75%, half bar) | As stated | W5, items 1–2; video | New `SHAPES` values |
| I3 | One-beat quadratic decay: does it read as a hit at 78 and 120 BPM? | Yes, as built | W5, item 3 | Change `ACCENT.decay_beats` or the curve |
| I4 | LEAD on a full family plays as DRAMATIC (a moving light, not a brighter one) | As stated | W5, item 4 | LEAD gets its own meaning on full families |
| I5 | SLOW, SMOOTH and FAST play as authored (SMOOTH no longer calms a template) | As stated (owner ruling 2026-11-12) | W5, item 5 | SMOOTH gets a calming shape |

## Colour, gobo and wheel tags (W1, W3/W4)

Video prefix: `planner_colour_*` and `side_by_side_*_planner_colour_*`.

| # | Question | Today | See | If answered the other way |
|---|---|---|---|---|
| C1 | **Wheel tag facts for the owner's fixtures:** which colour and gobo each slot shows | The owner's rig has no tags, so no colour or gobo is offered on it. Deriving tags from the owner's xLights layout is built, but it waits for the owner's word before it reads that layout | [W1](../evidence/2026-11-17-w1-profile-tags/README.md) | Paste the tags (paste-ready entries are printed), or authorize derivation from the layout |
| C2 | A colour change at a boundary the heads play straight through costs a short blackout (about 180 ms, at most half a beat) | As stated | [W3/W4](../evidence/2026-11-17-w3-w4-offer-colour/README.md#what-the-owner-should-look-for-w4-view-pending-owner), item 2; video | Keep colour changes to boundaries that already enter dark |
| C3 | A head whose wheel lacks the colour keeps the template's colour (white) | As stated | W3/W4, item 3 | Leave that head dark, or refuse the colour on mixed rigs |
| C4 | A palette colour the wheel lacks shows as the nearest slot, or not at all past a hue cap | As stated (`85595b98`) | W3/W4, item 5 | Change the hue cap or the grading |
| C5 | W1 tag rules: preset names accepted in `hex`; two states may share a colour or pattern; one shutter state per strobe speed; no strobe tag on open, closed or dark states (integrator, reversible) | As stated | W1, "Decisions" | Per rule |

## Events and lyric cues (W6/W7)

Video prefix: `events2_*`.

| # | Question | Today | See | If answered the other way |
|---|---|---|---|---|
| E1 | A hit on a full family: a dip into the beat, then a snap back to full | As stated (`HITS` contrasts 0.25/0.40/0.60) | [W6/W7](../evidence/2026-11-17-w6-w7-events/README.md#what-the-owner-should-look-for-w6w7-view-pending-owner), item 1; video | A brief blackout before the beat, or B (I1) |
| E2 | **Flash-and-duck** on a reveal (a cascade's hit from dark): a flash, then N frames ducked below the level | As stated (N = 2–4 frames, contrast capped at 0.40) | W6/W7, "Look questions for the owner", items 1–2 | Other N or cap; plain flash |
| E3 | **Hits on cascades light only 2 of the 4 heads** (those lit on the beat); a hit on a dark downbeat moves to the nearest beat where heads are lit | As stated; a cue-bound hit prefers the beat after its own when that beat is at or after the lyric | W6/W7, item 2; [W10b/c](../evidence/2026-11-18-w10bc-motif-variation/README.md) | Light the dark heads anyway (the viewer sees them fly back), or always prefer the later beat |
| E4 | Strobes are dark-first square waves (2/4/8 a beat); at 120 BPM `strobe_fast` is a hard flicker | As stated | W6/W7, item 3 | Other rates (`STROBE_FLASHES_PER_BEAT`) |
| E5 | **Strobe lighting a head in its template's dark phase:** the owner saw the break strobe's last flash light MH2/MH3 at frame 191 | A strobe only adds darkness, so it never lights a frame the template holds dark (0 cases in the probe). When an EXIT transition overlaps the strobe, the strobe's lit phases play over the transition's darkness, because a transition never cuts into a strobe span | [W10b/c](../evidence/2026-11-18-w10bc-motif-variation/README.md), "Strobe question"; video at frame 191 | Let a transition's darkness cut into a strobe. If the template itself closes the shutter there, it is a bug: send the render records |
| E6 | **`closed` without `open` holds to the section's end** | As stated (as the old renderer did) | W6/W7, item 4 | `closed` ends after a set length |
| E7 | A colour change on a cascade's dark beat waits for the next reveal (up to 2.3 s at 78 BPM). A change shown only briefly moves to a beat where it is shown for half a beat | As stated | W6/W7, item 5 and fix-round items; W10b/c | Dip and darken anyway, or drop the change |

## Transitions (W8)

Video prefix: `transitions2_*`.

| # | Question | Today | See | If answered the other way |
|---|---|---|---|---|
| T1 | CROSSFADE hands over at half the lower look's level (`CROSSFADE_FLOOR` 0.5) | As stated | [W8](../evidence/2026-11-17-w8-transitions/README.md#look-questions-for-the-owner-pending-owner), items 1, 7; video | Hold full and only move |
| T2 | MORPH moves from the start of the window; SWEEP holds, then travels | As stated | W8, item 2 | Different distinction |
| T3 | A colour change across a lit transition dips dark at the split point | As stated | W8, item 3 | FADE_VIA_BLACK by default at such boundaries |
| T4 | On cascades, a transition plays only on the heads lit at the boundary | As stated | W8, item 4 | The dark heads join it |
| T5 | **Crossfade from rest:** the first entry comes up from the rest pose; the intro stays dark until the split point, then eases onto its orbit as the light comes up | As stated | W8, items 6, 10 | Pre-position the heads and light them fully from the boundary |
| T6 | An event stays visible half a beat (a quarter beat after its lyric) before a darkening window starts; minimum window of 4 frames; a head that would lose a hit plays no transition | As stated | W8, items 8–9, 11–14 | Other margins; the transition wins over the hit |

## Motif and variation (W10a–c)

Video prefix: `motif5_*`. This is the latest; `motif*` to `motif4_*` are superseded and show known defects.

| # | Question | Today | See | If answered the other way |
|---|---|---|---|---|
| V1 | **`wide` ×1.5 and `fast` ÷2 (period halved):** are these the right amounts? | As authored for all seven families | [W10a](../evidence/2026-11-17-w10a-variants/README.md#look-questions-pending-owner), item 1; video | New catalog amounts; re-run the gate; re-pin |
| V2 | **Fitted strengths:** on slow heads the cascades play `wide` at ×1.2–1.4 and `fast` on a 3-beat period. Does that still read as the variation asked for? | Fitted to the rig, named in the offer and the trace | [W10b/c](../evidence/2026-11-18-w10bc-motif-variation/README.md), "Variant fitting" | Refuse the variation instead of fitting it |
| V3 | **Snap-and-hold as a variation carrier:** `finite_snap_hold`'s rate is barely visible (`fast` 0.5 beat, `slow` 2 beats against a 1-beat base) | Reach only. The gate drops a `fast` variant whose rate is invisible | W10a, item 2; W10b/c, "M1 design note" (options a/b/c) | (a) re-snap as a loop, (b) rate on the hold, (c) as today |
| V4 | **Motif source: the introducer or a chain?** | Every carrier steps from the motif's introducing section (integrator, 2026-11-18). Steps do not accumulate, so the "build" arc is lost | W10b/c, PENDING-OWNER items 3, 5; [plan](w10-arrangement.md) | Chain: each carrier steps from the previous one, so a last chorus can go further than the first |
| V5 | Do WIDEN and FASTER read as "the same idea, bigger or quicker" across templates? Are reach and rate enough to carry a motif? | As built | W10b/c, PENDING-OWNER items 1–2 | Carry more than reach and rate |
| V6 | At the halved period, a cascade's stagger is half a beat, so MH2/MH3 reveal on the off-beat eighth (D5) | As stated | W10b/c, "D5" | Keep the stagger on the beat |
| V7 | **The song outranks the arrangement:** a variation that makes any event worse gives way. The arrangement is built up from the reference in plan order, and the earlier section wins a tie (integrator) | As stated (`f9894cc8`, `934b2635`) | W10b/c, "revised (after 08c50a92)"; [decision](../../../memories/decisions/mh-song-outranks-the-arrangement.md) | The variation wins, and the events move or drop |
| V8 | Gate cost of the nine-variant grid (2.3–3.5×) | Full grid | W10a, item 3 | Drop the combinations |
| V9 | W10 integrator decisions I1–I7 (REST is dark; reach and rate carried across templates; equal motif ids; variation source; `wide`/`fast` for all families; modifier keys) | As in the plan | [W10 plan](w10-arrangement.md), "Integrator decisions" | Per decision |

## Density and modifiers (W10d/e)

Video prefix: `density_*`. There is no modifiers video yet: the owner's saved plan sets no modifiers.

| # | Question | Today | See | If answered the other way |
|---|---|---|---|---|
| D1 | **Density means light or movement?** | Light: REST is dark; SPARSE has half the heads alternating per cycle; BUSY adds an accent each bar. The planner describes the light | [W10 plan](w10-arrangement.md#7-pending-owner), item 1; [density evidence](../evidence/2026-11-18-w10d-density/README.md) | Density changes movement and the planner describes that behavior |
| D2 | Looks: SPARSE's alternation, BUSY's accent per bar, SPARSE on `finite_snap_hold` | SPARSE swaps pairs on a hard cut. BUSY adds a hit-shaped accent. | W10 plan, item 2 | Per look |
| D3 | Modifiers: their closed set and what each renders | Spread, direction and aim adjust the played template where admitted. | [modifier evidence](../evidence/2026-11-18-w10e-modifiers/README.md) | Per modifier |

## Song, grid and test songs

| # | Question | Today | See | If answered the other way |
|---|---|---|---|---|
| S1 | **Extend the beat grid over the song's tail?** | The tail past the last detected beat renders dark (Phase 2 P2.0 policy), and the planner prompt does not say so | [W2](../evidence/2026-11-17-w2-planner-contract/README.md), "Addendum: song structure clamped" | Extend the grid to the song's end, as the display already does ([decision](../../../memories/decisions/display-stays-lit.md)) |
| S2 | **Artist and title of `Dance Jams Final Audio.mp3`,** for the online lyrics lookup (authorized 2026-11-17) | The records name neither | [implementation brief](../implementation-brief.md), approvals | Lyric cues can be looked up for that song |
| S3 | Integrator decisions in the song-intent plan: transition length and mode as categories; `modifiers` carried by reach, rate and variation; null intensity or colour means "as authored"; wheel states tagged in the profile | As stated | [song-intent rendering](song-intent-rendering.md), "Integrator decisions" | Per decision |
| S4 | The three-arm experiment and Phase 5 (inventory F6) after the selector port | Not rescoped | [plan](phase-3-arrangement.md#three-arm-experiment-after-the-selector-port-what-the-owner-must-know--2026-11-16) | Rescope Phase 5's comparison |
