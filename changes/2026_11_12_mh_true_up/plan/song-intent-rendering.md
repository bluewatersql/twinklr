# Song-intent rendering — plan of record (2026-11-17)

Replaces task T1 of [phase-3-arrangement.md](phase-3-arrangement.md) and withdraws its
decision D7. Owner direction of 2026-11-17 (recorded there): the planner's song intent
must be rendered, not cut. A field leaves the planner contract only on the owner's word.

## The defect this plan fixes

At `24c22b79` the renderer applies four things from the plan: template, segment bars,
preset, section bounds. It accepts and ignores the rest and says so per section
(`sequencer/moving_heads/pipeline.py:1713-1726`). The renderer deleted in `0ec65d47`
(recoverable at tag `mh-last-with-legacy-renderer`, `5d50580c`) rendered more. The
cutover therefore regressed the product. Source: read-only gap inventory by an architect
agent, 2026-11-17, with file and line citations at both commits.

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
actions, whether a dimmer hit is possible, wheel change time). The planner is shown the
offer. The validator refuses a choice the rig cannot make, so the refinement loop
revises the plan. What only the render can find impossible is degraded and recorded in
the trace, never silent. A plan whose intent is all null renders today's bytes exactly;
that is the regression anchor for every step.

- **Colour (section).** Palette role → a stop of the song's macro palette (PRIMARY
  first stop, ACCENT second, WARM/COOL by hue, NEUTRAL lowest saturation); explicit
  colour → its canonical value; then the nearest tagged wheel state. Overrides the held
  colour of the section's steps; template overlays keep their own. The change rides the
  dark entry transaction. A wheel has a few fixed colours: approximation is recorded.
- **Gobo (section).** As colour, through a pattern tag.
- **Intensity.** A dimmer table scales pulse levels and envelope level, never to zero,
  so darkness and the gate are unchanged. DRAMATIC and INTENSE add a beat-locked pulse on
  musical phase. Motion intensity is `reach`/`rate` choosing an admitted preset.
- **Events.** CLOSED/OPEN → dark spans. STROBE/PULSE → dimmer pulse where the dimmer
  extinguishes (also visible in the xLights preview), else shutter pulse or a tagged
  strobe state; rates below latency plus settle are refused. HIT (new) → dimmer raised on
  lit frames, magnitude from the cue's emphasis. COLOR/GOBO events (new for colour) → an
  overlay whose mask ends on the beat so the reveal lands on it; spacing under the
  wheel change time is refused.
- **Lyric moment cues.** Binding to the snapped beat is kept for every event action. A
  referenced cue that no event realises is refused by the validator. A cue landing on a
  dark phase or a rest is recorded.
- **Transitions.** `entry`: DIP, FADE_IN, SWEEP (lit travel within speed, no wheel
  change; falls back to DIP, recorded). `exit`: HOLD, FADE_OUT, BLACKOUT. Length as
  BEAT, HALF_BAR or BAR. Code owns the curve.
- **Show.** One resolver for `run` and `show`: palette roles resolve through the macro
  palette in both. The macro focal role constrains intensity through a validator rule.
- **Motif, variation, density.** Planner-chosen fields, as the plan of record had them.
  `variation` stays a planner choice.

## Planner contract

Every existing intent survives; additions are HIT, COLOR events, entry/exit categories.
Measured by the architect at 2 union fields and 38 nodes against Claude's 16 and 68
(today 25 and 126, sent unenforced), so one provider-enforced call.

```
Plan{sections:[Section], overall_strategy}
Section{section_id, start_bar, end_bar, section_role, energy_level,
  parts:[Part{start_bar, template_id, reach:INHERIT|COMPACT, rate:INHERIT|SLOW, reasoning}] (1-3),
  intensity: SLOW|SMOOTH|FAST|DRAMATIC|INTENSE|null,
  color: PALETTE_PRIMARY..PALETTE_NEUTRAL | <ColorPreset values> | null,
  gobo: <GoboPattern values> | null,
  events:[Event{bar, beat, moment_cue_id|null,
                action: OPEN|CLOSED|STROBE_SLOW|STROBE_MEDIUM|STROBE_FAST|PULSE|HIT|COLOR|GOBO,
                color|null, gobo|null}],
  moment_cues:[cue_id], motif_id|null, variation: NONE|NARROW|WIDEN|SLOWER|FASTER,
  density: REST|SPARSE|BALANCED|BUSY,
  entry: DIP|FADE_IN|SWEEP|null, exit: HOLD|FADE_OUT|BLACKOUT|null,
  transition_length: BEAT|HALF_BAR|BAR|null, reasoning}
```

Integrator decisions (reversible; the owner may overrule any):

1. Transition length and mode are categories; the numeric `duration_bars`, `curve`,
   `fade_out_ratio` and per-channel overrides become code-owned. Reason: the project's
   boundary puts curves and durations in deterministic code.
2. The free-form `modifiers` list, which neither renderer ever read, is carried by the
   typed `reach`/`rate`/`variation` fields.
3. Null intensity means "as authored", so accepted output stays byte-identical.
4. Wheel states are tagged in the fixture profile; W1 first checks whether the xLights
   layout already names colour-wheel slots so the tags can be filled without hand work.
   A missing tag never guesses a colour: the option is not offered, with a paste-ready
   entry in the message.

## Work sequence

Each task: one implementing agent, a separate reviewing agent, integrator commit,
`make validate` green. Null-intent byte identity against the pins is checked in every
task. Tasks marked **view** end with a render for the owner; acceptance is the owner's.

| Task | Content | Proof |
|---|---|---|
| W0 | Intent-parity test harness: a fixed plan with every intent set; the tag's rendered effect of each intent recorded as facts (which channel changes, when); each later task turns one "not applied" into "applied" | Harness fails today for every regression row |
| W1 | Profile tags (`hex`, `pattern`, `strobe`) on discrete states; derive from the layout where possible | Tagless profile byte-identical |
| W2 | Contract above; prompts; validator; cue binder over events; selector emits it; old-shape plans refused by name; spec enforced on Claude | Schema size pinned; neutral plans render pinned bytes |
| W3 | Rig offer from the gate; prompt; validator refusals; cache key; offered wheel states in the entry-dip bound | Tagless rigs byte-identical |
| W4 | Section colour and gobo — **view** | Every wheel change inside a dark window |
| W5 | Intensity — **view** | Dark frames unchanged; levels scaled |
| W6 | Events without wheels, cue binding, emphasis — **view** | Accent on the snapped beat |
| W7 | Colour and gobo events — **view** | Reveal on the beat; spacing refusals |
| W8 | Entry and exit transitions — **view** | SWEEP→DIP fallback recorded |
| W9 | Show: palette and focal role — **view** (combined show) | — |
| then | Motif, variation, density (former T3–T5) | — |

One live Claude request proves the contract compiles (owner authorization of 2026-11-13,
minimum only, logged).
