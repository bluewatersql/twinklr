# Song-intent rendering — plan of record (2026-11-17)

Replaces task T1 of [phase-3-arrangement.md](phase-3-arrangement.md) and withdraws its
decision D7. Owner direction of 2026-11-17 (recorded there): the planner's song intent
must be rendered, not cut. A field leaves the planner contract only on the owner's word.

Revised the same day after an independent review: an explicit field mapping (W2 waits
for the owner's word on its narrower rows), intensity as identity by default, repair
instead of refusal, timing rules, W1's layout read owner-gated, the fate of T2 and T4,
and the W0 result.

## The defect this plan fixes

At `24c22b79` the renderer applies four things from the plan: template, segment bars,
preset, section bounds. It accepts and ignores the rest and says so per section
(`sequencer/moving_heads/pipeline.py:1713-1726`). The renderer deleted in `0ec65d47`
(recoverable at tag `mh-last-with-legacy-renderer`, `5d50580c`) rendered more. The
cutover therefore regressed the product. Source: the read-only
[gap inventory](../evidence/2026-11-17-song-intent-gap-inventory/README.md) by an
architect agent, 2026-11-17, with file and line citations at both commits; the W0
[intent-parity record](../evidence/2026-11-17-w0-intent-parity/README.md) measured what
the deleted renderer did with each intent.

| Intent | Deleted renderer (tag) | Now | Class |
|---|---|---|---|
| Template, segments, bars, preset | rendered | rendered | kept |
| Intensity → light | dimmer floor, ceiling and pulse period from a table (`handlers/dimmers/default.py:87,151`, `libraries/dimmer.py:55-59`) | not applied | **regression** |
| Section colour (palette role or explicit) | one static colour-wheel byte per section, fixed role table (`pipeline.py:146-157`, `handlers/wheels.py:31-59`), wheel turned while lit | not applied | **regression** |
| Macro palette colour, focal role → intensity (`twinklr show`) | nearest preset to the palette's first colour; LEAD/SUPPORT/REST → intensity (`show_coordination.py:511-551`) | not projected (`show_stages.py:63-68`) | **regression** |
| Shutter events incl. strobe, pulse | byte written at the event time (`compile/intent_resolution.py:43-117`); pulse by sample index | not applied | **regression** |
| Gobo events | byte at the event time, lit wheel turn | not applied | **regression** |
| Lyric moment cues bound to an event | event moved to the cue's snapped beat and rendered (`moment_cues.py:151-173`) | bound, then dropped | **regression** |
| `transition_in` | byte blend over an overlap (`compile/transition_planner.py:130-190`) | none (dark entry dip only) | **regression** |
| Intensity → motion | ignored | not applied | never rendered |
| Cue reference without an event; cue emphasis | not rendered | not rendered | never rendered |
| `transition_out` | never read | none | never rendered |
| Motifs, variation, density | not rendered | not rendered | never rendered (was T3) |

Why it was possible to regress without noticing: the old renderer's intent layer had no
counterpart on the surviving path, the cutover's proof was "the surviving path's bytes
do not change", and no check compared what the two renderers did with the same plan.

### W0 result

The W0 harness (`tests/regression/test_mh_intent_parity.py`, facts in
`tests/regression/baselines/mh_intent_parity.json`, reproducible with
`scripts/extract_mh_intent_parity.py`) holds 34 rows: 10 recorded only and **24 strict
xfails**, each failing on its own target assertion today:

| Task | Rows | Status |
|---|---|---|
| W4 | 5 (explicit colour; palette roles PRIMARY, ACCENT, WARM, COOL resolved through a supplied macro palette, PRIMARY ≠ ACCENT) | **green** (W4, 2026-11-17; xfails removed) |
| W5 | 4 (DRAMATIC, INTENSE; each also on a template that authors its own pulse) | **green** (W5, 2026-11-17; xfails removed) |
| W6 | 6 (CLOSED/OPEN, three strobes, PULSE, the cue-bound shutter event) | **green** (W6, 2026-11-17; xfails removed) |
| W7 | 3 (gobo event, two successive gobo events, the cue-bound gobo event) | **green** (W7, 2026-11-17; xfails removed; the parity rig's gobo states carry W1's `pattern` tags) |
| W8 | 4 (entry CROSSFADE, MORPH, SWEEP, FADE_VIA_BLACK; MORPH and SWEEP must differ) | strict xfail |
| W9 | 2 (show palette colour from a palette whose answer differs from the old fixed table; a LEAD section renders hotter than SUPPORT, REST no hotter) | show palette colour **green** (W4: `show` resolves palette roles through the macro palette, the resolver `run` uses); focal role **green** (W5: the show render moves the section's intensity a step by the heads' focal role) |

After W3/W4: 18 strict xfails remain (W5 4, W6 6, W7 3, W8 4, W9 1)
([record](../evidence/2026-11-17-w3-w4-offer-colour/README.md)). After W5: 13 (W6 6, W7 3,
W8 4) ([record](../evidence/2026-11-17-w5-intensity/README.md)). After W6/W7: 4 (W8 4)
([record](../evidence/2026-11-17-w6-w7-events/README.md)).

Findings that change the tasks:

- **The old section transitions did not play in the render measured.** The old
  renderer wrote its crossfades on a second xLights layer under untrimmed section
  effects. In the owner's 2026-11-16 viewing render of one song (the old-renderer
  reference `.xsq` from the code at `dcc14ddf`, read under the implementation brief's
  "viewing render and old-renderer reference: inputs" row), wherever the section layer's
  byte was non-zero the section layer played: every boundary between two sections played
  as a lit cut, including the default crossfade on a null hint. A zero section byte under
  a non-zero transition byte did not occur, so that case is unobserved. Frame data is in
  the W0 record. W8's target is therefore the planner's intent — a
  smooth lit change between sections — and is new visible behaviour, judged by the
  owner at the W8 view, not a restoration.
- **Intensity has no headroom on the catalog families.** They hold the dimmer at full.
  With "never below the authored look", DRAMATIC and INTENSE cannot raise a floor or add
  a pulse there. W5 must decide how intensity shows on a full-level template (for
  example a beat-locked dip-and-return pulse whose depth grows with the level, or
  authored levels in the families that leave headroom) and the owner judges it at the
  W5 view. Recorded for that view: the old renderer's SMOOTH turned an energetic
  template's 131–255 five-beat pulse into a 51–153 four-bar swell.
- **Old defects not carried over:** wheel turns while lit at section boundaries, the
  fixed palette-role table, the sample-index pulse, SNAP as a lit cut.

## What the renderer already has to build on

Named wheel states with settle times; dark transactions (a wheel turns only while the
head is dark and settles before the reveal, `compile/preposition.py`); `_dark_over_spans`;
`AttributeOverlay` masks; `DimmerPulse`, `ShutterPulse`, `VisibilityEnvelope.level`;
presets `narrow`/`slow`; shutter timing checks (`compile/step.py:826-869`). Template
authors drive these today; the planner does not. The physical profile cannot yet say
which wheel state is which colour or pattern, or which shutter state strobes.

## Design

The boundary holds: the planner picks categories; code owns time, DMX and physical
limits. The pre-planning gate publishes a per-rig **offer** (colours, gobos, shutter
actions, whether a dimmer hit is possible, wheel change time, and each template's dark
phases). The planner is shown the offer. A plan whose intent is all null renders today's
bytes exactly; that is the regression anchor for every step.

**No hard refusal of a paid plan.** Where the rig cannot do something the planner chose
(a colour or gobo not offered, a strobe rate under latency plus settle, wheel events
closer than the wheel change time, a referenced cue that no event realises, a cue on a
dark phase that cannot move), deterministic repair drops or adjusts that one item,
records it in the trace with its reason, and feeds it back to the planner on the next
refinement iteration. The run never fails for it. W2 builds and tests that loop.

- **Colour (section).** Palette role → a stop of the song's macro palette (PRIMARY
  first stop, ACCENT second, WARM/COOL by hue, NEUTRAL lowest saturation); explicit
  colour → its canonical value; then the nearest tagged wheel state. Overrides the held
  colour of the section's steps; template overlays keep their own. The change rides the
  dark entry transaction. A wheel has a few fixed colours: approximation is recorded.
- **Gobo (section).** As colour, through a pattern tag.
- **Intensity.** The most common level is the identity:
  - null and SMOOTH render as authored (byte-identical to today);
  - SLOW and FAST render as SMOOTH, as the old dimmer table did after the owner reverted
    the clean-up's dimmer ladder on 2026-11-12 (W0 record, Intensity);
  - DRAMATIC and INTENSE add a beat-locked pulse on musical phase and raise the dimmer
    floor; they never dim below the authored look, and dark frames stay dark, so the
    gate is unchanged.

  Motion is chosen through `reach`/`rate` (an admitted preset), not intensity. The table
  is the owner's to judge at W5's view.
- **Events.** CLOSED/OPEN → dark spans. STROBE/PULSE → dimmer pulse where the dimmer
  extinguishes (also visible in the xLights preview), else shutter pulse or a tagged
  strobe state; a rate below latency plus settle is repaired (above). HIT (new) → the
  dimmer raised on lit frames, magnitude from the cue's emphasis. COLOR/GOBO events (new
  for colour) → an overlay whose mask ends on the beat so the reveal lands on it; events
  closer than the wheel change time are repaired.
- **Lyric moment cues.** Binding to the snapped beat is kept for every event action. A
  referenced cue that no event realises is repaired and fed back. A cue landing on a
  dark phase or a rest is moved or recorded (timing rules below).
- **Transitions.** `entry` and `exit` are each a `Transition{mode: SNAP|CROSSFADE|MORPH|
  SWEEP|FADE_VIA_BLACK|BLACKOUT, length, curve}` (contract below); `entry` shapes the
  section's start, `exit` its end, over `length` (BEAT … EIGHT_BARS) eased by `curve`,
  and code places it on the grid. SNAP: no blend; the new look starts at the boundary,
  with a dark dip only where the head must reposition (today's entry). CROSSFADE: the
  dimmer hands over from the outgoing to the incoming look while lit, the aim moving
  within travel speed. MORPH: every continuous channel (pan, tilt, dimmer, zoom) eases
  from the outgoing to the incoming value, lit. SWEEP: the head travels lit to the
  incoming aim along a sweep at travel speed, distinct from MORPH's eased interpolation
  (W8 defines the path). FADE_VIA_BLACK: the dimmer fades to dark, wheels and aim change
  while dark, then it fades up. BLACKOUT: a cut to or from dark at the boundary. A
  CROSSFADE, MORPH or SWEEP that needs a wheel change or travel faster than the profile
  allows falls back to a dark dip, recorded in the trace.
- **Show.** One resolver for `run` and `show`: palette roles resolve through the macro
  palette in both. The macro focal role is applied deterministically at render time in
  `show`: code adjusts the section's effective intensity from the heads' focal role
  (LEAD hotter, REST no hotter than authored) and records it in the trace.
- **Motif, variation, density.** Planner-chosen fields, as the plan of record had them.
  `variation` stays a planner choice.

### Timing rules

- **Dark lead before a colour or gobo reveal** is bounded to half a beat (proposed). A
  change that needs longer dark before its reveal moves to the section entry, or is
  dropped with a trace record and fed back.
- **Dark phases are published.** The gate's offer lists each template's dark phases
  (visibility windows, overlay masks) per admitted variant, so repair can move a
  cue-bound accent to the nearest lit beat instead of losing it.
- **HIT forces a lit frame** on its beat. Where that beat falls inside a dark
  repositioning, repair moves the HIT to the nearest lit beat and records it.
- **A visible change at boundaries.** A section colour that differs from the previous
  section's needs the wheel to turn in the dark. Where a boundary plays lit today (the
  head plays through without an entry dip), a colour change forces a dark dip there.
  That is a look change for the owner to judge at the W4 view, not a defect.

## Planner contract

W2 measures the real schema size and pins it in a test before relying on one
provider-enforced call. The figure below (2 union fields, 38 nodes against Claude's 16
and 68; today 25 and 126, sent unenforced) is the architect's scratch measurement of a
draft, not a pinned figure.

```
Plan{sections:[Section], overall_strategy}
Section{section_id, start_bar, end_bar, section_role, energy_level,
  parts:[Part{start_bar, template_id, preset_id|null, reasoning}] (1-3),
  intensity: SLOW|SMOOTH|FAST|DRAMATIC|INTENSE|null,
  color: PALETTE_PRIMARY..PALETTE_NEUTRAL | <ColorPreset values> | null,
  gobo: <GoboPattern values> | null,
  events:[Event{bar, beat, moment_cue_id|null,
                action: OPEN|CLOSED|STROBE_SLOW|STROBE_MEDIUM|STROBE_FAST|PULSE|HIT|COLOR|GOBO,
                color|null, gobo|null}],
  moment_cues:[cue_id], motif_id|null, variation: NONE|NARROW|WIDEN|SLOWER|FASTER,
  density: REST|SPARSE|BALANCED|BUSY,
  entry: Transition|null, exit: Transition|null, reasoning}
Transition{mode: SNAP|CROSSFADE|MORPH|SWEEP|FADE_VIA_BLACK|BLACKOUT,
           length: BEAT|HALF_BAR|BAR|TWO_BARS|FOUR_BARS|EIGHT_BARS,
           curve: <the existing transition curve values>}
```

### Field mapping, old contract → new

**W2 does not start until the owner has seen this table and given their word on every
row marked "narrower".**

**Integrator revision, 2026-11-17 (overrides the rows below where they differ).** The
first draft of this table narrowed four rows. The owner's direction is that nothing the
planner can express is dropped, so the contract is changed instead of asking the owner
to accept the narrowing:

- **`preset_id` stays**, per part, as a string or null. The rig offer lists each
  family's admitted presets by name, so a `--template-dir` preset of any name is
  reachable and no combination is unreachable. `reach`/`rate` are not introduced.
  `variation` carries the planner's relation to the motif's source section; repair
  resolves it to an admitted preset or records that none fits.
- **Transitions keep their modes.** `entry` and `exit` are each a `Transition` with the
  old mode set (plus BLACKOUT), their own length, and the old curve choice as a
  category. Lengths cover the old 0–8 bar range as BEAT, HALF_BAR, BAR, TWO_BARS,
  FOUR_BARS, EIGHT_BARS. MORPH and SWEEP, which the old renderer drew identically, get
  distinct renderings in W8.
- **Still narrower, awaiting the owner's word:** (1) `modifiers`, the free key/value
  list neither renderer ever read; (2) the transition's `fade_out_ratio` (a 0–1 number
  placing the crossfade split) and per-channel overrides, which become code-owned. Until
  the owner answers, W2 keeps `modifiers` in the contract and maps `fade_out_ratio` to a
  split category (EARLY, EVEN, LATE); per-channel overrides wait for the answer.

W2 re-measures the schema with these fields before relying on one enforced call.

The old contract is `ChoreographyPlan`, `PlanSection`, `PlanSegment`, `ColorIntent`,
`ShutterEvent`, `GoboEvent`, `MomentCueReference`
(`agents/sequencer/moving_heads/models.py`) and `TransitionHint`
(`sequencer/models/transition.py`) at `24c22b79`. Marks: **kept** (as is);
**reshaped, same range** (new shape, nothing the planner could say is lost);
**reshaped, narrower** (something the planner could say is lost, named); **new**.

| Old field | New field | Mark | Notes |
|---|---|---|---|
| `ChoreographyPlan.sections` | `Plan.sections` | kept | |
| `ChoreographyPlan.overall_strategy` | `Plan.overall_strategy` | kept | |
| `PlanSection.section_name` | `section_id` | reshaped, same range | Renamed; it already held the unique `SongSectionRef.section_id` |
| `start_bar`, `end_bar` | `start_bar`, `end_bar` | kept | |
| `section_role` (free string or null) | `section_role` | kept | |
| `energy_level` (0–100 or null) | `energy_level` | kept | |
| `template_id` (unsegmented) XOR `segments` (1–3 `PlanSegment{segment_id, start_bar, end_bar, template_id, preset_id, modifiers, reasoning}`) | `parts` (1–3 `Part{start_bar, template_id, reach, rate, reasoning}`) | reshaped, same range | One part = an unsegmented section. Segments were already required to be contiguous and cover the section, so each part ends where the next starts. `segment_id` is derived in code. The XOR repair surface goes away |
| `preset_id` (free string, section or segment) | `reach: INHERIT\|COMPACT`, `rate: INHERIT\|SLOW` per part | **reshaped, narrower** | INHERIT/INHERIT → no preset (the family's effective variant on this rig and song); COMPACT/INHERIT → `narrow`; INHERIT/SLOW → `slow`; COMPACT/SLOW → **open point**: no catalog family declares a preset that is both (each declares exactly `narrow` and `slow`). Lost: naming any other preset. A `--template-dir` template whose presets have other names cannot have them chosen — **open point** for the owner (map by declared tags, add names, or accept) |
| `modifiers` (free key/value list, section and segment) | `reach`, `rate`, `variation` | **reshaped, narrower** | Neither renderer read them (gap inventory). Lost: free-form keys the planner could invent; the typed fields carry the meaningful ones |
| `reasoning` (section and segment) | `Section.reasoning`, `Part.reasoning` | kept | |
| `intensity` (required: SLOW\|SMOOTH\|FAST\|DRAMATIC\|INTENSE) | `intensity` (same values or null) | reshaped, same range | Null added: "as authored" (Design, Intensity) |
| `color_intent` = `{PALETTE_ROLE, palette_role: PRIMARY\|ACCENT\|WARM\|COOL\|NEUTRAL}` or `{EXPLICIT, explicit_color: 14 ColorPreset}` (required) | `color`: one enum of the 5 palette roles and 14 presets, or null | reshaped, same range | Both arms kept as one enum; null added ("as authored") |
| `shutter_events` (`bar`, `beat`, `pattern`: OPEN\|CLOSED\|STROBE_FAST\|STROBE_MEDIUM\|STROBE_SLOW\|PULSE, `moment_cue_id`) | `events` with `action` of the same six values | reshaped, same range | One event list for shutter, gobo, HIT and colour |
| `gobo_events` (`bar`, `beat`, `pattern`: 13 GoboPattern, `moment_cue_id`) | `events` with `action: GOBO`, `gobo` | reshaped, same range | |
| `moment_cues` (`[{cue_id}]`) | `moment_cues` (`[cue_id]`) | reshaped, same range | |
| `transition_in` (`TransitionHint` or null) | `entry` + `transition_length` | **reshaped, narrower** | Mode: SNAP → null (no blend; today's entry, with a dark dip only where the head must reposition); CROSSFADE, MORPH, SWEEP → SWEEP (lit travel into the section; DIP fallback recorded; the old renderer drew MORPH and SWEEP identically, W0); FADE_VIA_BLACK → FADE_IN here and FADE_OUT on the previous section's exit. `duration_bars` (0–8, continuous) → BEAT, HALF_BAR or BAR: lost, transitions longer than a bar and fractional lengths. `curve`, `fade_out_ratio`, `per_channel_overrides` → code-owned: lost, the planner's choice of easing, crossfade split and per-channel strategy |
| `transition_out` (`TransitionHint` or null; never read by either renderer) | `exit` + `transition_length` | **reshaped, narrower** | Mode: SNAP → HOLD; FADE_VIA_BLACK → FADE_OUT; CROSSFADE, MORPH, SWEEP → null (the next section's SWEEP entry carries the blend). BLACKOUT is new. Lost as for `transition_in`, and in/out lengths are one shared `transition_length` |
| — | `gobo` (section) | new | A section-level gobo, as section colour |
| — | `reach`, `rate` | new | (see `preset_id`) |
| — | `variation`, `density`, `motif_id` | new | Former T3 fields |
| — | `action: HIT` | new | An accent on lit frames, magnitude from the cue's emphasis |
| — | `action: COLOR` with `color` | new | Timed colour changes (the old contract had none) |
| — | `entry`, `exit`, `transition_length` | new | (see `transition_in`, `transition_out`) |

Integrator decisions (reversible; the owner may overrule any):

1. Transition length and mode are categories; the numeric `duration_bars`, `curve`,
   `fade_out_ratio` and per-channel overrides become code-owned. Reason: the project's
   boundary puts curves and durations in deterministic code. (Narrower rows above.)
2. The free-form `modifiers` list, which neither renderer ever read, is carried by the
   typed `reach`/`rate`/`variation` fields. (Narrower row above.)
3. Null intensity and null colour mean "as authored", so accepted output stays
   byte-identical.
4. Wheel states are tagged in the fixture profile. A missing tag never guesses a colour:
   the option is not offered, and the message carries a paste-ready entry. Deriving tags
   from an xLights layout is built and tested on a synthetic layout only; running it on
   the owner's layout waits for the owner's word (W1).

## What becomes of T2–T5

- **T2 (capability projection)** becomes **W3**, the rig offer from the gate (extending
  `SelectorAdmission`, as the plan required for T2).
- **T4 (deterministic reference selector)** emits the new contract in **W2**; its
  arrangement work comes after W9, with motif, variation and density.
- **T3 and T5** (arrangement, motif schedule) come after W9. T5a (moving heads in
  `twinklr show`) was done in C1.1a.

## Work sequence

Each task: one implementing agent, a separate reviewing agent, integrator commit,
`make validate` green. Null-intent byte identity against the pins is checked in every
task. Tasks marked **view** end with a render for the owner; acceptance is the owner's.
The branch is not merged before W9 lands unless the owner says otherwise: `main` still
has the renderer that applies song intent.

| Task | Content | Proof |
|---|---|---|
| W0 | Intent-parity test harness: a fixed plan with every intent set; the tag's rendered effect of each intent recorded as facts (which channel changes, when); each later task turns one "not applied" into "applied" | 20 regression rows fail today as strict xfails (above) |
| W1 | Profile tags (`hex`, `pattern`, `strobe`) on discrete states, with paste-ready guidance; a layout derivation tested on a synthetic layout only (reading the owner's layout is owner-gated, not yet authorized) | Tagless profile byte-identical |
| W2 | **Starts only after the owner's word on the field mapping.** Contract above; prompts; repair-and-feedback loop (tested); cue binder over events; selector emits it; old-shape plans refused by name; schema size measured and pinned; spec enforced on Claude; the stale "not applied … in Phase 1; the template renders as authored" diagnostic (`sequencer/moving_heads/pipeline.py:1719-1721`) and the `twinklr show` wording (`pipeline/show_stages.py:66-68`, diagnostic at `:189-200`) updated to say what is and is not applied | Schema size pinned; neutral plans render pinned bytes |
| W3 | Rig offer from the gate (former T2), including each template's dark phases; prompt; repair rules; cache key; offered wheel states in the entry-dip bound | Tagless rigs byte-identical |
| W4 | Section colour and gobo — **view** (includes the boundary dips colour changes force) | Every wheel change inside a dark window |
| W5 | Intensity — **view** (the owner judges the table) | Dark frames unchanged; null, SMOOTH, SLOW, FAST byte-identical; DRAMATIC/INTENSE never below authored |
| W6 | Events without wheels, cue binding, emphasis — **view** | Accent on the snapped beat |
| W7 | Colour and gobo events — **view** | Reveal on the beat; dark lead within half a beat; spacing repaired |
| W8 | Entry and exit transitions — **view** | SWEEP→DIP fallback recorded |
| W9 | Show: palette and focal role — **view** (combined show); the focal role applied at render and traced | The two W9 parity rows |
| then | Motif, variation, density (former T3–T5); T4's arrangement work | — |

**Consequences to tell the owner before merge.** W2's contract change re-keys the
moving-head planner caches (every song plans again once, paid) and makes plan
checkpoints and live plans recorded in the old shape unreadable: `eval-report` and
`regenerate` refuse them by name until the command that planned them runs again.

One live Claude request proves the contract compiles (owner authorization of 2026-11-13,
minimum only, logged).
