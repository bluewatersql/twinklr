---
type: review
status: complete
area: engineering
change: 2026_11_12_mh_true_up
created: 2026-11-17
updated: 2026-11-17
---

# Song-intent gap inventory — 2026-11-17

**Provenance.** Read-only analysis by an architect agent, 2026-11-17, comparing the
deleted moving-head renderer at tag `mh-last-with-legacy-renderer` (`5d50580c`) with the
current renderer at `24c22b79`. It wrote no code. The text below is its final report,
reproduced verbatim from the agent's transcript; only its headings were moved down one
level to sit under this title. Its line citations are at those two commits.

Its recommendations (design, contract shape, schema figures, work sequence, owner
questions) are input, not decisions. Where they differ from
[song-intent rendering](../../plan/song-intent-rendering.md), the plan of record is
current. Its schema-size figures are scratch measurements that W2 measures and pins.

---

### Summary

The current renderer (HEAD `24c22b79`) uses only four pieces of the planner's output: the template, the segment bar ranges, the preset and the section bounds. Everything else is accepted and then ignored, and a per-section diagnostic says so (`pipeline.py:1713-1726`). The deleted renderer (tag `5d50580c`) did render the following into DMX:
- intensity, through dimmer level and pulse;
- section colour, as a colour-wheel byte;
- timed shutter and gobo events;
- lyric moment cues, but only where they were bound to a shutter or gobo event;
- `transition_in` blends;
- in `twinklr show`, the macro palette colour and focal-role intensity.

Each of those is now a regression. All of them can be rendered on the current path by reusing machinery that already exists: named wheel states, dark transactions with wheel settle, `_dark_over_spans`, `AttributeOverlay` masks, `DimmerPulse`/`ShutterPulse` and `VisibilityEnvelope.level`. I recommend one reshaped planner contract that keeps every intent. I measured it at **2 unions / 38 nodes**, against today's 25/126 and Claude's limits of 16/68, so one provider-enforced call is enough. Behind it sits a rig "offer" from the pre-planning gate and a deterministic resolver per intent. A plan whose intent is all null renders today's bytes exactly.

Marks: **[V tag]** = verified at `mh-last-with-legacy-renderer` (`5d50580c`); **[V HEAD]** = verified at `24c22b79`; **[M]** = measured in this session; **[I]** = inferred, not verified.

### Analysis

#### 1. Intent inventory — what reaches the planner (all [V HEAD])

| Intent | Where it comes from | What the prompt tells the model | How it is validated |
|---|---|---|---|
| Sections, bars, tempo, meter | Audio profile and BeatGrid (`context.py:168-236`) | Song structure table and beat grid (`user.j2:21-35`) | Coverage and bar checks (`heuristic_validator.py:351`); section-id canonicalisation (`moment_cues.py:72-107`) |
| Overall energy, creative guidance, section objectives | Audio profile | `user.j2:55-100` | None |
| Lyric `MomentCue` (`cue_id`, `timestamp_ms`, `section_id`, emphasis LOW/MED/HIGH, text, `visual_hint`) | Lyrics agent (`lyrics/models.py:158-180`), filtered to the section (`stage.py:333-345`) | Listed with their emphasis (`user.j2:121-126`). "For a cue-driven shutter or gobo accent set its `moment_cue_id`" (`user.j2:193-195`) | Cue exists and belongs to the section (`moment_cues.py:13-32`); timestamp inside the section (`:110-142`) |
| Key phrases, story beats, mood arc | Lyrics agent | Shown as prose (`user.j2:106-120`) | Not referenceable by the plan |
| Macro palette arc and section palette, motifs, focal arc, energy target, motion density, choreography style, coordination intent | `MacroPlan` (`planning/models.py:166-222`) | Table plus "choose templates that complement this mood" (`user.j2:129-154`). Only `palette_id` is shown, never its colours (`context.py:252-258`) | None in the MH validator |
| `template_id`, `segments`, `preset_id` | Planner (`models.py:148-223`) | `developer.j2:24-75` | Library membership (`heuristic_validator.py`); preset admission (`stage.py:563-568`) |
| `intensity` (SLOW/SMOOTH/FAST/DRAMATIC/INTENSE) | Planner (`models.py:230`) | "from the enum" (`developer.j2:79`, `user.j2:188`) | Schema only |
| `color_intent` (palette role or explicit `ColorPreset`) | Planner (`models.py:37-103`) | "use the discriminator" (`developer.j2:80-81`) | Schema only; the planner is never told whether the rig has a colour wheel |
| `shutter_events`, `gobo_events` (bar, beat, pattern, `moment_cue_id`) | Planner (`models.py:122-145`) | `developer.j2:82-83`, `user.j2:191-192` | Inside the section, cue reference known (`models.py:337-354`); bar/beat rebound to the cue time (`moment_cues.py:151-173`, via `orchestrator.py:348`) |
| `moment_cues` (list of references) | Planner | `developer.j2:84-87` | Unique ids, known cues |
| `transition_in`, `transition_out` (`TransitionHint`: mode, `duration_bars`, curve, `fade_out_ratio`, per-channel overrides) | Planner (`models.py:224-229`, `transition.py:69-145`) | Only "populated or null" (`developer.j2:105`) and "plan smooth transitions" (`user.j2:163`) | Schema only. It alone costs 7 unions / 26 nodes [M] |
| `section_role`, `energy_level`, `modifiers`, `reasoning`, `overall_strategy` | Planner | `developer.j2:97-132` | Range checks only |

#### 2. What the deleted renderer did with each [V tag]

- **Intensity.** `_resolve_section_intent` (`pipeline.py:2362-2396`) passed it into `apply_template_intent` (`compile/intent_resolution.py:21-40`, called at `template_compiler.py:184`).
  - **Dimmer: rendered.** The dimmer table chose floor, ceiling and pulse period (`handlers/dimmers/default.py:87,151`; `libraries/dimmer.py:55-59`): SLOW = SMOOTH = FAST at 0–128 with a 4-bar period; DRAMATIC 100–255 at 1.25 bars; INTENSE 150–255 at 0.25 bar.
  - **Movement: not rendered.** The handler reads `params["intensity"]` and defaults to SMOOTH (`handlers/movement/default.py:80-86`), and the old audit reported it as ignored (`diagnostics.py:227-252`).
  - A preset id spelled as an energy word also became a dimmer-intensity preset (`pipeline.py:138-143,165-223`).
- **Colour: rendered as one static wheel byte for the whole section.**
  - Palette roles went through a fixed table: PRIMARY→RED, ACCENT→MAGENTA, WARM→AMBER, COOL→CYAN, NEUTRAL→WHITE (`pipeline.py:146-157`). The song's palette was not used.
  - The byte came from `dmx_mapping.color_map`. A missing name, or a fixture with no colour channel, fell back to "open" (`handlers/wheels.py:31-59`). The default map has no amber, so WARM rendered open (`config/fixtures/dmx.py:97-110`).
  - The wheel turned while the head was lit (no masking).
- **Shutter events: rendered.** Each event split the segments at its time and wrote the `shutter_map` byte, which persisted until the next event (`intent_resolution.py:43-117`, called at `template_compiler.py:310`; time from `pipeline.py:2398-2410`).
  - The strobe bytes 64/127/190 were defaults unless the rig configured its own (`dmx.py:15-24`).
  - PULSE alternated closed/open by **sample index**, not musical time (`wheels.py:95-116`).
  - Events were dropped for a shutter on a channel above 16 (`wheels.py:16,85-92`).
  - Nothing checked latency or settle.
- **Gobo events: rendered the same way** through `gobo_map`. The default map is `open`/`gobo1-4`, so a pattern name such as "stars" fell back to open unless the rig named its slots (`dmx.py:116-125`, `wheels.py:122-150`).
- **Moment cues: rendered only through events.** An event's bar/beat was rebound to the cue timestamp snapped to the nearest beat (`moment_cues.py:151-173`) and then rendered as that shutter or gobo change. A reference with no event, and the cue's emphasis, were never rendered.
- **`transition_in`: rendered.** It was on by default (`config/models.py:604`) and used at `pipeline.py:1761,1845-1851,2463`. The overlap honoured `duration_bars`, `fade_out_ratio` and curve (`transition_planner.py:130-190`) and blended **constant source/target bytes** per channel (`transition_segment_compiler.py:150-200`). Pan and tilt therefore moved while lit, with no speed check. `transition_out` was never read.
- **`twinklr show`.** The planner's colour was overwritten with the nearest preset to the section palette's first colour, and intensity was set from the focal role: LEAD→INTENSE, SUPPORT→SMOOTH, REST→SLOW (`show_coordination.py:69-73,511-551`, called at `show_stages.py:242-249`). Segments were sliced to the coordination windows (`show_coordination.py:593-635`).
- **Never rendered:** `section_role`, `energy_level` and `modifiers` were read only by the validator and reports. The tag's own physical path also applied no intent (`pipeline.py:2061`).

#### 3. What the current renderer does [V HEAD]

- **Applied:** template, preset or effective variant (`pipeline.py:1298-1350`), section bounds, segments (via flattening), the BeatGrid and phase map.
- **Not applied, stated per section:** intensity, colour, shutter and gobo events (`pipeline.py:1713-1726`). Transitions are gone; `transitions` is refused as a removed job field (`config/models.py:676-678`).
- **Show path:** the macro palette and focal role are explicitly not projected (`show_stages.py:63-68,194-195`). Only the coordination rests survive, as dark spans (`pipeline.py:189-282`).
- **Moment cues:** binding still runs (`orchestrator.py:348`), so a cue moves an event that is then never rendered.
- **Capabilities the renderer has, which only the template author drives today:**
  - Steps (`models/template.py:460-516`): `color`, `gobo` and `shutter_state` as named profile states; `shutter` (`ShutterPulse` between two states, `:249-253`); `dimmer` (`DimmerPulse` low/high/period/duty, `:236-240`); `visibility` (lit phase window and `level`, `:256-281`); `zoom` (`:290-306`); `component_refs` to rig attribute presets (`:350-361`).
  - Template overlays (`AttributeOverlay`, colour or gobo, with dark masks, `:317-347`; compiled at `template_compiler.py:779`).
  - Presets `narrow` and `slow` on every family.
  - The catalog uses almost none of this: no family sets `color` or `gobo`. The only wheel use is `masked_wheel_flick`'s overlay to the rig preset `flick` (`catalog/templates/moving_heads/masked_wheel_flick.json:44-55`).
- **Physical profile** (`config/fixtures/capabilities.py`):
  - Axes: pan, tilt, dimmer, zoom (`:35`), with travel speed, latency and settle (`:94-104`).
  - Discrete channels: shutter, colour, gobo (`:36`), with named states, each having a byte and `settle_ms` (`:239-270`).
  - Visibility: dimmer-zero extinguishes, extinguishing shutter states, close/open latency (`:326-345`).
  - Missing: anything that says what colour a slot is, what pattern a gobo is, or which shutter state is a strobe.
- **Physical rules:** a wheel turns only after the head is dark and settles before the reveal (`compile/preposition.py:1-29,127-133`). A shutter change faster than its latency plus settle is rejected (`compile/step.py:826-869`). The gate's entry-dip bound assumes any wheel state the admitted rungs hold (`pipeline.py:549-553`).
- **Owner rig** (`evidence/2026-11-16-p3-real-audio-gate/README.md:25-31`): colour wheel on ch1, gobo ch4, shutter ch2, dimmer ch3, no zoom. Wheel settle is 150 ms; dark + turn + settle takes 420 ms (`:50`). The xLights preview ignores the shutter, so darkness shows only through the dimmer (`viewing-render/README.md:94`).

#### 4. Gap table

Classes: (a) regression against the deleted renderer; (b) never rendered by either; (c) rendered by both.

| Intent | Old renderer | Current | Capability exists now | Class |
|---|---|---|---|---|
| Template, segments, bars, beat grid | Rendered | Rendered | — | (c) |
| `preset_id` | Declared preset, or energy-word auto preset | Declared/admitted, else effective variant | — | (c); the energy-word path is (a), closed by intensity |
| Intensity → light | Dimmer table | — | Dimmer pulse, envelope `level` | **(a)** |
| Intensity → motion | Ignored | — | `narrow` / `slow` presets | (b) |
| Section colour (role or explicit) | Static wheel byte from a fixed table | — | Step `color`, dark wheel transactions | **(a)** |
| Macro palette colours | `show` only: nearest preset to the first colour | — | As above | **(a)** |
| Focal role → intensity | `show` only | — | Dimmer | **(a)** |
| Shutter events, incl. strobe and pulse | Static bytes; pulse by sample index | — | `ShutterPulse`, dark spans, timing checks | **(a)** |
| Gobo events | Static byte, lit wheel turn | — | Step `gobo`, `AttributeOverlay` masks | **(a)** |
| Cue-bound events | Rendered at the snapped beat | Bound, then dropped | As events | **(a)** |
| Cue reference with no event; `emphasis` | — | — | Dimmer | (b) |
| `transition_in` | Byte blend | — (dark entry dip only) | Envelope attack, dimmer ramp, dark windows | **(a)** |
| `transition_out` | — | — | Dimmer ramp, dark span | (b) |
| Coordination rests | Segment slicing | Dark spans | — | (c) |
| Motifs, variation, density | — | — | Presets, dark masking | (b), planned in T3 |
| `section_role`, `energy_level`, `modifiers` | — | — | — | (b), not visual controls |

### Root Cause

1. C1.2 deleted the whole resolution layer and built no equivalent on the surviving path: `_resolve_section_intent`, `intent_resolution.py`, the wheel handlers, and the transition planner and compiler. That path was built in Phase 1 to defer intent ([V tag] `pipeline.py:2061`), and D7 kept it deferred.
2. The physical profile cannot say which state is red, which is the stars gobo, or which is a strobe. Categories therefore have nothing to resolve to [V HEAD].
3. The 25/126 contract does not fit Claude's limits, which pushed the T1 draft toward cutting fields instead of reshaping them [M].

### Recommendations

#### A. Design per gap, on the single path

The planner picks categories; deterministic code resolves them after compile and before `_enter_section`, so the transaction pass sees final visibility; the gate publishes what each rig can do; the validator refuses what is statically impossible, so the refinement loop revises the plan; anything the render finds impossible is degraded and recorded in the trace.

**Rig offer (new; extends `TemplateAdmission` or the selector's projection, no second projection):**
- Profile tags, never defaulted:
  - colour states: `hex`;
  - gobo states: `pattern` (a `GoboPattern` value);
  - shutter states: `strobe` (slow/medium/fast).
- The offer lists, per fixture: the colours and gobos it can show, the shutter actions available, whether HIT is available (needs a dimmer axis), and `wheel_change_ms` (dark + turn + settle) in ms and in beats.
- **The entry-dip union must include every offered wheel state.** Otherwise the gate's entry bounds become wrong.
- The planner prompt shows the offer; the cache key hashes it.
- [I] xLights DMX models may already define colour-wheel slots that could fill `hex`; not verified.

**Colour (section).**
- Resolution: a palette role maps to a stop of the song's macro palette, reusing `get_palette`, which already resolves the same palette for the display branch (`show_coordination.py:265-269`). Stop policy: PRIMARY is the first stop, ACCENT the second, WARM/COOL by hue, NEUTRAL the lowest saturation (chosen, not measured). Without a macro plan, the role uses the old fixed table. An explicit preset uses its canonical hex. Either way the result is the nearest tagged wheel state, with ties broken by state name.
- Composition: overrides the held `color` of every step and component preset in the section. Template overlays keep their own state over their windows. Null means as authored.
- The change rides the existing dark entry transaction. [I] a wheel change makes the entry "not as authored", so a dark window opens; W4 must test this.
- Refused: a non-null colour on a rig with no offer. Degraded and recorded: mixed rigs, and nearest-slot distance.
- Only partly renderable: a wheel has a few fixed colours, no mixing, and no lit colour change.

**Gobo (section):** the same as colour, through the pattern tag.

**Intensity (proposed W5).**
- A dimmer table scales `DimmerPulse` high/low, the envelope `level` and component dimmer levels, and never produces zero, so darkness and the gate are unchanged.
- DRAMATIC and INTENSE add a beat-locked pulse, as the old table did, but on musical phase.
- Null means as authored. This keeps every pin byte-identical. The table values are chosen, not measured.
- Only partly renderable: there is no headroom above an authored full level, so a HIT in such a section becomes a flick (recorded).
- Motion intensity stays with `reach` / `rate` → `narrow` / `slow` (D4). FAST and WIDE need variants the catalog does not have, and 150°/s caps the owner rig.

**Events (proposed W6-W7).**
- **CLOSED / OPEN:** dark spans through `_dark_over_spans`, including its `shortest_lit_ms` rule.
- **STROBE_\* / PULSE:** a dimmer pulse when the profile's dimmer extinguishes (visible in the xLights preview); otherwise a `ShutterPulse`, or a tagged strobe state. Checked by `_check_pulse_widths` and `_check_shutter_timing`. A rate below latency plus settle is refused by the validator.
- **HIT (new):** the dimmer is raised only on frames that are already lit; emphasis LOW/MED/HIGH sets the magnitude in code.
- **COLOR / GOBO events:** a synthetic overlay through `_apply_overlays` whose mask ends on the beat, so the reveal lands on it.
  - Refused: spacing under `wheel_change_ms` from the section edges or another wheel event.
  - Only partly renderable: on the owner rig a change needs about 420 ms; at 78 BPM a beat is about 766 ms, so it fits.
- **Moment cues:** binding is kept for every action.
  - Refused by the validator: a referenced cue that no event realises, or a cue inside the family's `entry_dips` bound (`pipeline.py:549-553`).
  - Degraded and recorded: a cue that lands on a dark envelope phase or a coordination rest.

**Transitions (proposed W8).** These become categorical, since the planner must not own durations.
- `entry`: DIP (today's behaviour), FADE_IN (envelope attack after the reveal), SWEEP (lit travel within speed and with no wheel change; degraded to DIP and recorded when infeasible).
- `exit`: HOLD, FADE_OUT (dimmer ramp before the transaction), BLACKOUT (a dark span over the last beat, which also gives the entry more time).
- Removing the numeric `duration_bars`, `curve`, `fade_out_ratio` and `per_channel_overrides` needs the owner's word. Option: keep length as `BEAT | HALF_BAR | BAR` (+1 node).

**Show (proposed W9).** One resolver for both: in `run` and `show` alike, palette roles resolve through the macro palette. The old focal-role override is replaced by a validator rule (REST excludes DRAMATIC and INTENSE; LEAD excludes SLOW), pending the owner's word.

**`section_role` / `energy_level`:** kept as required fields (removing the null drops a union); cross-checked against the family's energy range and the macro section; recorded in the trace.

**`modifiers`:** its free-form role moves into the typed `reach` / `rate` fields. Dropping the free-form list needs the owner's word.

#### B. Schema budget [M; scratch script measured with `claude_json_schema` / `claude_schema_size` at HEAD]

- Today's model is 25 unions / 126 nodes; `TransitionHint` alone is 7/26.
- `Literal[..., None]` compiles to one `enum` that includes null: **0 unions**. A `Color | None` alias produces `anyOf` and counts as a union.
- The proposed contract measures **2 unions / 38 nodes**, so one provider-enforced call is enough and no split is needed.

```
Plan{sections:[Section], overall_strategy:str}
Section{section_id, start_bar, end_bar, section_role:str, energy_level:int,
  parts:[Part{start_bar, template_id, reach:INHERIT|COMPACT, rate:INHERIT|SLOW, reasoning}] (1-3),
  intensity:SLOW|SMOOTH|FAST|DRAMATIC|INTENSE|null,
  color:PALETTE_PRIMARY..PALETTE_NEUTRAL|RED..UV(all 14 ColorPreset)|null,
  events:[Event{bar, beat, moment_cue_id:str|null, action:OPEN|CLOSED|STROBE_SLOW|STROBE_MEDIUM|STROBE_FAST|PULSE|HIT|COLOR|GOBO,
                color:<same enum>|null, gobo:<13 GoboPattern>|null}],
  moment_cues:[str], motif_id:str|null, variation:NONE|NARROW|WIDEN|SLOWER|FASTER,
  density:REST|SPARSE|BALANCED|BUSY, entry:DIP|FADE_IN|SWEEP|null, exit:HOLD|FADE_OUT|BLACKOUT|null, reasoning}
```

- Every current value survives: both colour arms, every shutter and gobo pattern, cue references, and transitions (as categories).
- Additions that need the owner's word: HIT, COLOR events, null intensity.
- The node proxy ignores enum size, so one live probe is still needed. That is a paid call and owner-gated: PENDING-OWNER.

#### C. Sequenced work (replaces T1; each step ends with `make validate` green)

1. **W1 Profile tags** (small). Add `hex` / `pattern` / `strobe` to `DiscreteState`, validated per channel.
   - Accept: a profile without tags loads unchanged; bytes are identical.
   - Tests: profile model tests; the 360-configuration byte matrix.
2. **W2 Contract.** The model above; prompts edited; `flatten` working on parts; the binder over `events`; validator rules (action/field pairing, every referenced cue realised); the selector emits the new shape; `legacy_intent_omitted` and the legacy normalisers removed; the spec added to `_CLAUDE_COMPILED_SPECS`.
   - Accept: within 16/68; neutral plans render the pinned bytes (`tests/regression/test_mh_pins.py`); old-shape saved plans are refused by name.
   - Tests: `test_models`, `test_structured_outputs`, `test_prompts`, `test_specs`, moment-cue and selector tests.
3. **W3 Rig offer.** Gate output, prompt section, validator refusals, cache key, offered wheel states inside the entry-dip union.
   - Accept: tagless rigs are byte-identical. On tagged rigs, if entry dips move, bump `RENDERER_REVISION` and tell the owner.
4. **W4 Section colour and gobo.**
   - Test: every wheel-byte change falls inside a dark window that covers close latency before and settle after; null gives today's bytes.
   - **Owner viewing.**
5. **W5 Intensity.**
   - Test: the set of dark frames is unchanged and levels are scaled.
   - **Owner viewing.**
6. **W6 Events without wheels** (CLOSED/OPEN, STROBE, PULSE, HIT, cue binding, emphasis).
   - Tests: the accent lands on the snapped beat; dark-frame accents are recorded, not rendered; strobe uses the dimmer when the dimmer extinguishes, else the shutter.
   - **Owner viewing.**
7. **W7 COLOR/GOBO events:** reveal on the beat; spacing refusals.
   - **Owner viewing.**
8. **W8 Entry and exit**, including SWEEP→DIP degradation.
   - **Owner viewing.**
9. **W9 Show**: palette through the macro plan; focal-role validator rule.
   - **Owner viewing** of a combined show.
10. Then T2–T5 as planned. T2 is folded into W3. The motif fields already exist after W2. The diagnostic at `pipeline.py:1713-1726` is removed when W8 lands.

### Trade-offs

| Option | Pros | Cons |
|---|---|---|
| Null intent = as authored | Pins and accepted look hold; byte-identity is a clean anchor | No headroom for HIT at full level |
| Intensity table with headroom (SMOOTH below full) | Accents can brighten | Changes the accepted look; pins need the owner's word |
| Validator refuses un-offered options | Refinement loop fixes the plan; nothing silent | One more refinement round; the prompt grows |
| Static enums plus per-rig offer in the prompt | Schema stays stable and within limits | Planner can pick an un-offered value, caught only by the validator |
| Dimmer-first accents | Visible in the xLights preview and on the rig | Not a true strobe for lamps that cannot strobe by dimmer [I] |
| Categorical transitions | Fits the boundary and the budget | The planner loses numeric length and curve (owner's word) |
| Mapping colour by nearest wheel slot | Deterministic, uses the song's palette | Palette colours a wheel lacks render approximately (recorded) |

### References (worktree `/Users/ondeck/work/github/twinklr-mh-true-up`)

**At the tag (`5d50580c`):**
- `packages/twinklr/core/sequencer/moving_heads/pipeline.py:146-157, 165-223, 1761, 1845, 2362-2410, 2463, 2061` — palette table, energy-word preset, transitions, intent resolution, physical-path diagnostic
- `.../compile/intent_resolution.py:21-117`, `.../compile/template_compiler.py:184, 310` — section intent and timed events
- `.../handlers/wheels.py:16-150`, `.../handlers/movement/default.py:80-86`, `.../handlers/dimmers/default.py:87, 151`, `.../libraries/dimmer.py:55-59` — wheels, ignored movement intensity, dimmer table
- `packages/twinklr/core/config/fixtures/dmx.py:15-24, 97-125` — default shutter, colour and gobo maps
- `packages/twinklr/core/sequencer/moving_heads/diagnostics.py:227-252` — movement intensity reported as ignored
- `packages/twinklr/core/sequencer/show_coordination.py:69-73, 511-551, 593-635`, `packages/twinklr/core/pipeline/show_stages.py:242-266` — show palette and focal-role projection
- `.../compile/transition_planner.py:130-244`, `.../compile/transition_segment_compiler.py:150-200` — transition blend

**At HEAD (`24c22b79`):**
- `/Users/ondeck/work/github/twinklr-mh-true-up/packages/twinklr/core/sequencer/moving_heads/pipeline.py:189, 283, 537-561, 1298-1350, 1713-1726` — dark spans, section entry, gate result, preset choice, unapplied-intent diagnostic
- `/Users/ondeck/work/github/twinklr-mh-true-up/packages/twinklr/core/agents/sequencer/moving_heads/models.py:28-433` — planner response model
- `/Users/ondeck/work/github/twinklr-mh-true-up/packages/twinklr/core/agents/sequencer/moving_heads/moment_cues.py:35-173` — cue binding
- `/Users/ondeck/work/github/twinklr-mh-true-up/packages/twinklr/core/agents/sequencer/moving_heads/prompts/planner/developer.j2:77-88` and `user.j2:102-196` — what the planner is told
- `/Users/ondeck/work/github/twinklr-mh-true-up/packages/twinklr/core/sequencer/models/template.py:236-516` — step, pulse, envelope, zoom, overlay models
- `/Users/ondeck/work/github/twinklr-mh-true-up/packages/twinklr/core/config/fixtures/capabilities.py:35-36, 239-345` — profile axes, discrete states, visibility
- `/Users/ondeck/work/github/twinklr-mh-true-up/packages/twinklr/core/sequencer/moving_heads/compile/step.py:279-295, 826-869` and `compile/preposition.py:1-29, 120-133` — held states, shutter timing, dark transactions
- `/Users/ondeck/work/github/twinklr-mh-true-up/packages/twinklr/core/pipeline/show_stages.py:63-68, 194-195` — show path does not project palette or role
- `/Users/ondeck/work/github/twinklr-mh-true-up/packages/twinklr/core/agents/providers/anthropic.py:81-155` — schema limits and size measure

**Scratch measurement:** `/private/tmp/claude-501/-Users-ondeck-work-github-twinklr/9cfb5b66-fff4-47db-adcb-766b50dc61e9/scratchpad/measure3.py`

### Owner decisions needed before W2

1. Transition durations and curves become categories.
2. `modifiers` become typed `reach` / `rate`.
3. Add HIT and COLOR events.
4. Null intensity means as authored, or a headroom table instead.
5. Tag wheel states by hand, or derive them from the xLights layout (feasibility unverified).

No field is cut by this design.
