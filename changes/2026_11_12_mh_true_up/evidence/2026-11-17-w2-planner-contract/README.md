---
type: evidence
status: complete
area: engineering
change: 2026_11_12_mh_true_up
created: 2026-11-17
updated: 2026-11-17
---

# W2 — the song-intent planner contract

**Provenance.** Implemented by an executor agent on 2026-11-17 in the worktree
`twinklr-mh-true-up`, branch `feat/mh-true-up-p3`: first from `10f3ac49` (integrated as
`1f953f96`), then a fix round on `85595b98` answering the independent review of
`1f953f96` (REQUEST CHANGES, items 1-14 below). Uncommitted; the integrator commits.
Plan of record: [song-intent rendering](../../plan/song-intent-rendering.md), task W2,
under the owner's ruling that nothing the planner can express, and nothing song-aware,
is dropped. No provider call, no xLights, no owner data. Where the plan's sketch and the
W2 brief differ, the brief was followed; the differences are listed below.

W2 reshapes the contract only. It renders no intent: every plan renders the bytes its
equivalent rendered at `10f3ac49` (proof below).

## The contract (`agents/sequencer/moving_heads/models.py`)

One response model, `ChoreographyPlan`, replaced in place. No legacy normalisers, no
second model, no switch.

```
ChoreographyPlan{sections: [PlanSection] (>=1), overall_strategy: str}
  (+ repairs: [PlanRepair], code-owned, not in the response schema; see Repair)
PlanSection{section_id, start_bar, end_bar, section_role: str|null, energy_level: 0-100|null,
  parts: [PlanPart{start_bar, template_id, preset_id: str|null, modifiers: [{key, value}],
                   label: str|null, reasoning}] (1-3),
  intensity: SLOW|SMOOTH|FAST|DRAMATIC|INTENSE|as_authored,
  color: PALETTE_PRIMARY|PALETTE_ACCENT|PALETTE_WARM|PALETTE_COOL|PALETTE_NEUTRAL
         |red|blue|green|yellow|magenta|cyan|orange|purple|amber|lime|white|warm_white|cool_white|uv|as_authored,
  gobo: open|circles|triangles|stars|diamonds|clouds|prism|shatter|dots|flame|water|foliage|abstract|as_authored,
  moment_cues: [cue_id],
  events: [PlanEvent{bar, beat, moment_cue_id: str|null,
                     action: open|closed|strobe_slow|strobe_medium|strobe_fast|pulse|hit|color|gobo,
                     color: <colour vocabulary>|none, gobo: <gobo vocabulary>|none}],
  motif_id: str|null, variation: NONE|NARROW|WIDEN|SLOWER|FASTER,
  density: REST|SPARSE|BALANCED|BUSY,
  transitions: [PlanTransition] (0-2: at most one ENTRY, one EXIT),
  reasoning}
PlanTransition (sequencer/models/transition.py){edge: ENTRY|EXIT,
  mode: snap|crossfade|morph|fade_via_black|sweep|blackout,
  length: BEAT|HALF_BAR|BAR|ONE_AND_HALF_BARS|TWO_BARS|THREE_BARS|FOUR_BARS|SIX_BARS|EIGHT_BARS,
  curve: <CurveLibrary, 41 values>,
  split: QUARTER|THIRD|HALF|TWO_THIRDS|THREE_QUARTERS   (the outgoing look's fade-out share),
  channels: [ChannelTransition{channel: pan|tilt|dimmer|shutter|color|gobo,
                               strategy: snap|smooth|crossfade|fade_via_black|sequence}] (0-6)}
```

- **"No choice" is a string member, not null** (after the live probe, below). A section's
  `intensity`, `color` and `gobo` take `as_authored` to keep the template's own look; an
  event's `color` and `gobo` take `none` when its action does not use them. Each is a
  plain `{"type": "string", "enum": [..., "<sentinel>"]}`, the sentinel last; no enum lists
  null and none sits under a type list, so one schema form is valid on every provider and
  costs no union. In Python the sentinel is `None` (an `Annotated` type: a
  `BeforeValidator` reads the sentinel as `None`, a `PlainSerializer` writes `None` as the
  sentinel, `WithJsonSchema` derives the enum from the vocabulary), so consumers, repair,
  the selector, reports and the parity block keep testing `is None`; Python callers may
  still pass `None`. **Every dump, and so the hashed form, spells the sentinel**
  (`"as_authored"`, `"none"`), in JSON and Python modes alike. The prompts ask the planner
  to answer the song and to give a reason for any `as_authored` (Prompts below).
- The other optional fields (`section_role`, `energy_level`, `preset_id`, `label`,
  `moment_cue_id`, `motif_id`) stay `anyOf` string/integer or null, the form the
  already-probed registered schemas use.
- **In-model rules (context-free only):** bar order and 1-indexing; parts start at the
  section's start, are strictly ordered and start inside the section; 1-3 parts; moment
  cue ids unique and not blank; at most one ENTRY and one EXIT; each transition channel
  once. Event and part strings are stripped (`moment_cue_id` and `label`, blank → null).
  **Action/field pairing is no longer a model rule** (review item 3): it is repaired, so a
  paid response is never refused for one event.
- **Parts and labels.** A part plays until the next part starts. `part_ids` names each
  part by its `label`, else `A`/`B`/`C` by position (a label or letter already taken in
  the section gives way to the first free letter). `flatten_section` turns a section into
  the renderer's sections: **timing labels** (the section timing marks in the `.xsq` and
  `.xtiming`, and the trace's section ids) are therefore:

  | Section | Timing label(s) |
  |---|---|
  | one part, no label | `<section_id>` |
  | one part labelled `X` | `<section_id>\|X` |
  | several parts, labelled | `<section_id>\|<label>` each |
  | several parts, unlabelled | `<section_id>\|A`, `\|B`, `\|C` |

  This is byte-compatible with the old contract: an old section without segments gave
  `<id>`, an old segment `X` gave `<id>|X` (one segment included), and the matching new
  part is unlabelled or labelled `X` (review item 8). The ENTRY transition goes to the
  first part, the EXIT to the last; events to the part whose bars hold them; moment cues
  to every part.
- **Saved plans in the old shape** are refused by name (`load_plan`): "this moving-head
  plan was saved in the planner contract before 2026-11-17 ... To write it again,
  <remedy>". No reader for the old shape.

### Differences from the plan's sketch

| Sketch / brief | Implemented | Why |
|---|---|---|
| `entry: Transition\|null, exit: Transition\|null` | `transitions: [PlanTransition{edge, ...}]`, at most one of each; `section.entry` / `section.exit` read them | The pair costs 7 more nodes: at the first measure it hit Claude's node limit exactly. Hoisting the transition into one list keeps the full range (0 or 1 entry, 0 or 1 exit) |
| per-channel strategy "in categorical form" | `channels: [{channel, strategy}]` (each channel once) | Six nullable fields as an object cost 74 nodes, over the limit; the list says the same |
| `modifiers` on the section | `modifiers` on each **part** | The old contract had them on the section and on each segment; per part keeps segment modifiers, and section modifiers are every part's |
| Upper-case action, colour and mode spellings | Existing vocabularies keep their own spellings; palette roles `PALETTE_<ROLE>`; new categories upper-case | Every old value is accepted under its old spelling |
| `section_role`, `energy_level` | kept nullable | The old fields were nullable |
| (review item 8) | `PlanPart.label` | The planner's own segment words survive in timing labels |

## Measured schema size (pinned in `tests/unit/agents/test_structured_outputs.py`)

Measured with the project's `claude_json_schema` / `claude_schema_size` and
`strict_schema_stats`, after every change of the fix round:

| | Claude unions (limit 16) | Claude nodes (limit 68) | OpenAI properties | depth | enum values |
|---|---|---|---|---|---|
| Old contract (`10f3ac49`) | 25 | 126 | 55 | 7 | 94 |
| First W2 (`1f953f96`, typeless nullable enums) | 5 | 57 | 39 | 7 | 161 |
| Fix round (`897c4501`, enums typed `["string","null"]`: **refused live**) | 11 | 60 | 40 | 7 | 166 |
| **After the probe fix (sentinel members)** | **6** | **60** | **40** | **7** | **166** |

The sentinel members cost no union and no node (enum size is free in the node count). The
six unions are the optional `section_role`, `energy_level`, `preset_id`, `label`,
`moment_cue_id`, `motif_id`. Margin: 10 unions, 8 nodes. Response-schema hash
`50a67e62…dca39877` (was `a76326c7…8683a9` at `10f3ac49`).
`test_no_registered_strict_schema_has_an_untyped_enum` and
`test_no_registered_schema_sent_to_claude_uses_a_form_claude_refuses` guard every
registered spec. The generic "type every bare enum" rule the fix round added to
`schema_utils.py` is reverted: nothing needs it now.

**Scan of every registered spec for the probe's hazard** (an enum listing null, or an
enum under a type list): none has it (asset_prompt_enricher, audio_profile, lyrics,
group_planner, section_judge, holistic_corrector, holistic_judge, mh_planner, mh_judge,
macro_planner, macro_judge, vision_judge, show_vision_judge); no other agent's schema
changed.

`mh_planner` is in `_CLAUDE_COMPILED_SPECS`: by measure it is within the limits and the
provider sends it as `output_config.format`. Its first live compile was refused (Live
probe, below); the fixed schema's live compile is pending the integrator's next request. The
oversize-schema provider tests use `MacroPlan` (8 / 83, still over).

## Field mapping, old contract (`10f3ac49`) → W2, as implemented

Marks: **kept**; **reshaped, same range** (the two transition rows: same range, quantised to steps); **new**. There is no narrower row.

| Old field | New field | Mark | Notes |
|---|---|---|---|
| `ChoreographyPlan.sections` | `sections` | kept | |
| `ChoreographyPlan.overall_strategy` | `overall_strategy` | kept | Required (the default came from a removed normaliser) |
| `PlanSection.section_name` | `section_id` | reshaped, same range | Renamed; it already held the unique section id |
| `start_bar`, `end_bar` | same | kept | |
| `section_role` (str\|null) | same | kept | |
| `energy_level` (0-100\|null) | same | kept | |
| `template_id` XOR `segments` (1-3 `PlanSegment{segment_id, start_bar, end_bar, template_id, preset_id, modifiers, reasoning}`) | `parts` (1-3 `PlanPart{start_bar, template_id, preset_id, modifiers, label, reasoning}`) | reshaped, same range | One part = unsegmented. Segments had to be contiguous and cover the section, so a part's end is the next part's start |
| `PlanSegment.segment_id` (free string) | `PlanPart.label` (free string\|null) | reshaped, same range | The planner's word is the label; null takes a letter. Timing labels as before (table above) |
| `preset_id` (section or segment, free string) | `PlanPart.preset_id` | kept | Admission decides validity; a `--template-dir` preset of any name stays choosable |
| `modifiers` (section and segment) | `PlanPart.modifiers` | reshaped, same range | |
| `reasoning` (section and segment) | `PlanSection.reasoning`, `PlanPart.reasoning` | kept | |
| `intensity` (required, 5 values) | `intensity` (5 values or `as_authored`) | reshaped, same range | `as_authored` added (None in Python) |
| `color_intent` (`PALETTE_ROLE` + 5 roles, or `EXPLICIT` + 14 presets) | `color` (5 `PALETTE_*` + 14 presets, or `as_authored`) | reshaped, same range | Both arms in one enum (tested equal to `PaletteRole` and `ColorPreset`) |
| `shutter_events[]` (`pattern`: 6 values; `moment_cue_id`) | `events[]`, `action` of the same 6 values | reshaped, same range | |
| `gobo_events[]` (`pattern`: 13 `GoboPattern`; `moment_cue_id`) | `events[]`, `action: gobo` + `gobo` (13 values; `none` on other actions) | reshaped, same range | |
| `moment_cues[{cue_id}]` | `moment_cues[cue_id]` | reshaped, same range | |
| `transition_in` (`TransitionHint` or null) | `transitions[edge=ENTRY]` | reshaped, same range | Same 5 modes and `CurveLibrary`; `per_channel_overrides` → `channels` list |
| `transition_out` | `transitions[edge=EXIT]` | reshaped, same range | Its own length (not shared) |
| `TransitionHint.duration_bars` (0-8) | `length`: 9 steps, BEAT (¼ bar in 4/4) … EIGHT_BARS, including 1½, 3 and 6 bars | reshaped, same range, quantised to steps | Review item 13: the whole old range in finer steps; a value between steps snaps to the nearest (1.25 bars → BAR or ONE_AND_HALF_BARS); code owns the exact milliseconds |
| `TransitionHint.fade_out_ratio` (0-1) | `split`: QUARTER, THIRD, HALF, TWO_THIRDS, THREE_QUARTERS | reshaped, same range, quantised to steps | Review item 14; a value between steps snaps to the nearest. The old model's default 0.5 is HALF; the W0 parity fixture's 0.25 is QUARTER |
| — | `gobo` (section), `action: hit`, `action: color` + `color`, `mode: blackout`, `motif_id`, `variation`, `density`, `as_authored` for intensity/colour/gobo | new | |

Removed with their callers (rule 9; no other importer, config or doc reader):
`PlanSegment`, `ColorIntent`/`ColorIntentKind`/`PaletteRoleColorIntent`/
`ExplicitColorIntent`, `ShutterEvent`, `GoboEvent`, `MomentCueReference`,
`flatten_plan_segment`, every `_normalize_legacy_*` validator and `legacy_intent_omitted`;
`TransitionHint`, `ChannelTransitionOverrides`; `libraries/shutter.py` (`ShutterPattern`,
its values now `EventAction`'s); `lyric_moment_cue_errors` (replaced by repair).
**Restored in the fix round** (review item 2, owner's standing ruling): the deterministic
selector's song-aware policy (`SelectorConfig.intensity_cutoffs`, `accent_roles`,
`neutral_roles`; `_intensity`, `_palette_role`; `SelectionTrace.unresolved_intent_fields`),
now mapped onto `intensity` and `color = PALETTE_<role>`, with its tests (the family test,
the round trip, and new energy→intensity and role→palette tables). It was unread only
because the renderer ignores intent; the missing piece is the reader.

## Repair rules (`moment_cues.bind_lyric_moment_cues`)

The normaliser runs on every planner response before validation. **Structural** problems
still raise and go through the refinement loop: a section id naming no song section, a
display name naming several, a song section used twice; then the heuristic validator: a
template not offered, a section beyond the song, overlapping sections. Everything else is
**one item**, and repair keeps as much of the planner's intent as the song can hold,
recording each as `PlanRepair{section_id, item, action: dropped|adjusted|recorded, reason}`:

| Item | Repair |
|---|---|
| A part label repeating an earlier part's | cleared; the part takes a letter (adjusted) |
| A `moment_cues` id naming no lyric cue, a cue of another section, or a cue whose timestamp lies outside its own section | reference dropped |
| A `color` event with no colour, a `gobo` event with no gobo | dropped (nothing left to do) |
| A colour or gobo on an event whose action does not use it | cleared (adjusted) |
| An event bound to an unusable cue | unbound, keeps its own bar and beat (adjusted) |
| An event bound to a usable cue the section does not list | the reference is added (adjusted) |
| An event bound to a usable cue | moved to the section's beat nearest the cue: the cue's own nearest beat, or, when that lies in a neighbouring section (a cue at 7.9 s nearest the next section's downbeat), the section's first or last beat (adjusted, recorded) |
| … when the section has no beat on the grid | dropped |
| … when there is no beat grid | keeps its binding and its own position (recorded) |
| An unbound event before / after the section | moved to its first beat / its last beat (adjusted) |
| An event on a beat its bar does not have | moved to the bar's last beat (adjusted) |
| Events of one kind (shutter, hit, colour, gobo) on one beat | one kept (tie-break below); each other dropped and named (a duplicate, or the kept one) |
| (same-beat conflict tie-break) | a cue-bound event first, then one repair did not change, then the first |
| A referenced cue no event lands on | recorded, with the fix: "add an event with moment_cue_id '…' that matches its emphasis, or remove the reference" (nothing synthesised) |

The run never fails for one item. Repairs reach the judge (in the plan JSON), the next
refinement prompt (controller hook `plan_repairs`; `user_refinement.j2` now tells the
planner how to fix an unrealised cue), the render trace (`plan_repairs`, only when there
are any), the `eval-report`, and survive a regeneration.

**Advisory: an unanswered high-emphasis cue** (review item 5). Repairs reach the planner
only on a refinement round, so a valid plan that leaves a HIGH lyric moment cue of a
planned section without an event is now sent back: the controller's new
`plan_advisories` hook (`moment_cues.unanswered_high_cues`) returns one line per such cue;
the first time, while a planning round remains, the plan goes back to the planner with
those lines as its fixes before any judge call. It resends **at most once per run**
(`IterationContext.advisory_sent`), so it cannot consume the judge's rounds; otherwise the
plan is judged as it is. It never fails a run. Tested with the provider mocked
(`test_an_unanswered_high_cue_sends_a_valid_plan_back_while_rounds_remain[2|1]`, and
`test_the_advisory_resends_at_most_once_so_the_judge_keeps_its_rounds`: a planner ignoring
the advice twice is judged on round 2, and the judge's revise verdict gets round 3).

## Prompts (review item 6)

Both packs edited in place so that answering the song is the default and a null is the
exception that needs a reason. The model still picks categories only; code owns timing
and DMX. Key passages, before (`1f953f96`) → after:

**Planner developer, Song Intent.** Before:
> Song intent says how a section should answer the song on top of that. **Null, or an
> empty list, means "as the template is authored."** Set a field only when it serves the
> music; leaving it null is a valid, deliberate choice.

After (Plan Structure, as of the probe fix):
> **Every section answers the song.** Set `intensity` from its energy target, a
> palette-role `color` from its palette, and answer every high- and medium-emphasis lyric
> moment cue and every drop and hit with an event chosen to fit the section (see
> Proportion). Choose `as_authored` for `intensity`, `color` or `gobo` only when you can
> say in `reasoning` why the template's own look already answers this moment; leave an
> event list empty only for the same reason. A plan whose sections are mostly
> `as_authored` ignores the song.

plus: what `section_role` and `energy_level` are for and that `reasoning` must name the
energy, palette colour, cues and moments answered; intensity read from the energy target
(`LOW` → SLOW/SMOOTH, `MED` → SMOOTH/FAST, `HIGH` → FAST/DRAMATIC, `BUILD` → a step up and
rising, `PEAK` → DRAMATIC/INTENSE, `RELEASE` → a step or two down; "Intensity that stays
flat across a clear change of energy ignores the song"); which palette role suits which
section; events on every drop, hit and stop; every high- and medium-emphasis cue answered,
the action matched to the emphasis; motif `variation` and `density` shaping the arc
across repeated sections; transitions mapped to boundaries (`snap` into a drop or on a
downbeat hit, `blackout` into a drop after a stop or a dead stop, `fade_via_black` into a
quiet bridge or outro, `crossfade` / `morph` between related sections, `sweep` on builds
and lifts; length against the phrase: a beat or half a bar for a cut-like change, one or
two bars between phrases, four to eight bars across a long phrase); four new "common
errors" (unanswered cue or drop, flat intensity, a named colour without reason, an
all-null section without reason).

**Planner system.** Before: "Leave song intent as the template authored it unless a
choice serves the music." After: "**Answer this song**: Every section's light follows this
song: intensity from its energy, colour from its palette, accents on its lyric moments and
its drops and hits, transitions shaped to its boundaries. A template on its own is
generic; the song intent is what makes it this song's. Leave a choice to the template only
when you can say why its own look already answers the moment."

**Planner user.** Before: "Leave a field null (or a list empty) wherever the template as
authored already serves the music." After: a "Song Intent: Answer This Song" checklist
(intensity from the energy target, a palette role from the Section palettes, an event on
every high- and medium-emphasis cue listed for the section and on drops, hits and stops,
`section_role`/`energy_level`, motif and variation across repeats, a transition per shaped
boundary, "A section that keeps the authored look (`as_authored`) needs a reason there.").

**Judge developer.** Before: "Song-intent fields that are null or empty mean 'as the
template is authored'; that is valid, not missing" and "…left as authored where the
template already serves?". After: an `as_authored` intensity, colour or gobo or an empty
event list is "schema-valid, but judged in Phase 2 as a choice that needs a reason"; Musical Synchronization requires a cue-bound event for every
high-emphasis cue and intensity that follows the energy targets; **Penalise** an
unanswered high-emphasis cue (and unanswered medium ones), flat intensity across a clear
energy change, colour that ignores the palette, and mostly-`as_authored` plans ("cannot score above
the soft-fail band"); **Reward** reasoning that cites the lyrics (cue ids and text),
energy targets and palette colours. The judge now sees the lyric moment cues
(`build_judge_variables` passes `lyric_context`; `judge/user.j2` lists them) and the
section palettes.

**Proportion** (second review). The planner developer prompt has a Proportion paragraph,
and the "answer every cue" sentences now say the answer is chosen to fit the section:
> **Proportion.** Answering the song is not making the show busy. Accents are punctuation:
> give each section a few, spaced so each one lands, and save strobes and the highest
> intensity for the builds and the peak, so the biggest moment is the biggest thing in the
> show. In a quiet section answer a medium-emphasis cue with a colour or gobo change or a
> soft pulse, not a strobe. Hold a colour across a section and change it where the palette
> or the mood turns. Contrast makes the chorus land: a restrained verse is part of
> answering the song.

The user prompt's checklist says the same in short; the judge penalises "a plan that is
busy rather than responsive: strobes or the highest intensity in low-energy sections,
accents too dense to read, colour changes faster than the music changes, no contrast
between verse and chorus."

Pinned by `test_prompts.py` (`test_the_planner_is_told_to_answer_the_song_in_every_section`,
`test_the_judge_penalises_a_plan_that_ignores_the_song`,
`test_no_pack_nudges_the_model_toward_leaving_the_song_unanswered`, which forbids
"valid, deliberate choice", "leaving it null is", "unless a choice serves the music",
"left as authored where", "that is valid, not missing" and similar). Emphasis is written
"high-/medium-emphasis" in prose because the project's guard forbids hand-listing two
taxonomy enum values on one prompt line. The schema's field descriptions were reworded the
same way ("from the section's energy (as_authored: the template's own, with a reason)").

## Consumers

| Consumer | Change |
|---|---|
| Renderer (`pipeline.py`) | Iterates `flatten_section` (labels as above). The per-section diagnostic now separates what regressed from what no renderer has rendered (review item 9): "section 's1': the planner's song intent is not rendered yet; intensity, colour, shutter and gobo events, their lyric cue binding, entry transition: a known regression (the renderer before the single-renderer cutover rendered them); section gobo, hit and colour events, exit transition, motif, variation, density, modifiers: not rendered by any renderer yet. Both are being fixed under changes/…/song-intent-rendering.md; the template renders as authored" (only the parts that apply). `plan_repairs` in the record |
| Identity | Plan dump with canonical template ids per part |
| `check_regeneration_base`, regeneration merge | Per part; repairs merged |
| Deterministic selector | One part per section with its effective variant, intensity from energy, palette role from section role (restored) |
| Three-arm experiment | Admission per part |
| Evaluation report | `SectionReport.song_intent`, markdown "Song intent (as planned)", `RenderSummary.plan_repairs`; old checkpoints refused by name |
| Vision evaluation | Every intent field in the judge's per-section line |
| Live plan load | Old-shape records refused by name ("run `twinklr inject`") |
| Show stage | Palette/focal-role diagnostic worded as a known regression |
| Planner context | Each macro section's palette colours (`palette_colors`) |
| Iteration controller (shared) | `plan_repairs` and `plan_advisories` hooks (default off for other agents) |
| Heuristic validator | Per part, located by part id |

## User-visible changes and re-keying

- **Every song plans again once.** The planner cache key hashes the response schema
  (`spec_prompt_hash` → `response_schema_hash`, `a76326c7…` → `50a67e62…`) and the prompt
  packs (`cfb07167…` → `8a67005a…`); no manual bump is needed
  (`test_the_response_schema_re_keys_the_plan_cache`). The first `run`/`show`/`inject` per
  song is a paid planning call; a plan that leaves a high-emphasis cue unanswered can take
  one more planner call (bounded by `max_iterations`).
- **Old checkpoints** are refused by `eval-report` by name (re-run the command that planned
  them); **old live plans** by `regenerate` (run `twinklr inject`). The two historical
  checkpoints under `evaluations/` stay as history.
- **On Claude** the plan is sent schema-enforced (live compile pending the probe).
- Renders, timing tracks and sidecars are byte-identical for equivalent plans; **render
  fingerprints change** (the hashed plan dump changed). Timing labels: as the table above.

## Byte proof (re-run after the fix round)

Scripts are session-local (not committed): `<w2>` =
`/private/tmp/claude-501/-Users-ondeck-work-github-twinklr/9cfb5b66-fff4-47db-adcb-766b50dc61e9/scratchpad/w2`.
`<w2>/matrix_w2.py` (from the C1.4 matrix) ran on `git archive 10f3ac49` and on this tree,
each building plans in its own contract; `<w2>/tools/compare_w2.py` compared them.
360 configurations (8 rigs incl. the zoom pilot, 3 fixture timings, 5 grids incl. 3/4 and
silent edges, 3 policies) × 3 plans:

- **A**: every admitted family, no presets; **B**: reversed, alternating `narrow`/`slow`;
- **C**: a section of two parts **labelled** `pickup`/`drop` (old: segment ids
  `pickup`/`drop`), a section of two **unlabelled** parts (old: `A`/`B`), and a **one-part
  section labelled** `tail` (old: one segment `tail`); every song intent set (DRAMATIC,
  SLOW, an explicit and a palette-role colour, a strobe and a gobo event, a crossfade
  entry with split QUARTER).

Result: 1,080 renders, 20,250 leaves. **Identical**: frames, returned segments, gate
admissions, normalised record and trace, `.xsq`, `.xtiming`, `.xmap` of every render.
**Different by design only**: the fingerprint, the raw record and raw trace (fingerprint,
reworded intent diagnostic, normalised to its presence per section). The deterministic
selector's plans (3 seeds, 8 sections), with intensity and colour restored, render
byte-identical frames, segments, `.xsq`, `.xtiming`, `.xmap` (`<w2>/selector_bytes.py`).

Pins: the 44 frame hashes and both `.xsq` hashes unchanged; the 44 fingerprints and the
combined-show golden's moving-head fingerprint re-recorded again
(`tests/golden/fixtures/combined_show_drop.json`: `3be80a97…` at `10f3ac49` →
`b2583195…`); its effects and trace hashes unchanged.

Intent parity: only the "Plans and calls" block changed (now with `label` and the finer
length/split mapping), plus `overall_strategy=""` on the anchor's plan construction; no
assertion, row id or xfail marker changed. Normal: 2 passed, 24 xfailed. `--runxfail`:
anchor passes, all 24 rows fail on the same assertion line with a byte-identical message
as at `10f3ac49` (`<w2>/tools/parity_compare.py`).

## Live probe (prepared, not run)

`probe_planner.py` (this folder): the real rendered planner pack for a synthetic song (the
unit tests' four-section, 90 s, 120 BPM profile and macro plan, palette
`core.christmas_traditional`; three synthetic moment cues, MED, HIGH, LOW; the family
catalog), **one** `AnthropicProvider.generate_json_async` call to `claude-opus-5-5` with
the production planner's reasoning effort (`high`) and token budget (50,000), no
prompt-only fallback, SDK retries off on both clients (review item 10).

```bash
# Dry run (default): builds the exact request, prints sizes, sends nothing.
uv run python changes/2026_11_12_mh_true_up/evidence/2026-11-17-w2-planner-contract/probe_planner.py
# The one paid request (owner-authorized, minimum only; ANTHROPIC_API_KEY set):
uv run python changes/2026_11_12_mh_true_up/evidence/2026-11-17-w2-planner-contract/probe_planner.py --live --out probe_result.json
```

It exits non-zero unless the response was provider-enforced (`json_schema`), validates as
a `ChoreographyPlan`, and has no validator errors; it prints the effort used, usage, the
song intent per section, the repair count and each repair, and any unanswered HIGH cue
(the dry run exits non-zero if the schema would not be sent enforced). Dry run on this
tree: schema 6 / 60, 10,941 bytes, no Claude schema hazard; developer 27,737, system 4,890,
user 8,381 characters; `schema_enforced True`; request 54,681 bytes; exit 0. The probe now
catches a provider refusal and exits 1 with its message.

## Live probe (2026-11-17)

The integrator sent the one authorized request after committing `897c4501`:
`probe_planner.py --live`, 2026-11-17T14:30:51Z, request id
`req_011Ch8fJpv3DhpHFfhp6KGYs`, log `probe_live.log` in this folder. Purpose: prove
Claude compiles and enforces the 11 / 60 schema on the real rendered planner pack.
Result: **HTTP 400**, no tokens generated:

> output_config.format.schema: Invalid schema: Enum value 'PALETTE_PRIMARY' does not match
> declared type '['string', 'null']'

Claude does not accept an `enum` under a list-valued `type`. What changed:
- the five nullable enums became plain string enums with a sentinel member (`as_authored`
  for the section's intensity, colour and gobo; `none` for an event's colour and gobo),
  `None` in Python, the sentinel in every dump (Contract above);
- `claude_schema_hazards` (`agents/providers/anthropic.py`) encodes the lesson, with the
  provider's message quoted: an enum under a type list, or an enum listing null, is
  refused before any request is sent (`_build_request` raises), and a test holds every
  registered schema to it;
- prompts say `as_authored` / `none` where they said null; the probe catches a provider
  refusal and exits 1;
- the schema is 6 unions / 60 nodes; fingerprints re-recorded; the byte proof re-run.

One further request will be sent by the integrator after this fix.

## Live probe 2 (2026-11-17): compiled, degenerate plan; offline diagnosis

The integrator's second request (log `probe_live_2.log`, response `probe_response.json`,
schema `50a67e62…`): Claude compiled and enforced the schema (`json_schema`, 14.6 s,
21,042 prompt / 1,218 completion tokens, `end_turn`). The plan was one section, `intro`
bars 1-7, with `reasoning` and `overall_strategy` both `"x"`, and no lyric cue answered.
The probe reported it clean (`validator_errors []`, `unanswered_high_cues []`, exit 0).

### Why it passed (reproduced offline, no request)

`probe_planner.py --replay probe_response.json` runs the saved response through what
production runs after the provider returns (`ChoreographyPlan` validation, the normaliser,
`create_validator_function`, `unanswered_high_cues`). Run against the tree before this
round, it gives no error:

| Check (before) | Result on the probe 2 plan |
|---|---|
| validator errors | `[]` |
| warnings | `Section 'intro' end_bar (7) doesn't match song structure (8)`; `Plan doesn't cover all song sections: chorus, outro, verse` |
| `unanswered_high_cues` | `[]` (it looked only at planned sections) |

Three defects, all older than W2 (the same code is at `10f3ac49`; the structure's bar
arithmetic dates from 2026-02-03), none lost by W2:

1. **Coverage and bar mismatches were warnings**, and the controller sends back errors only.
2. **The validator keyed song sections by display name** (`verse`, `chorus`), plans by
   `section_id` (`verse_1`), so a planned `verse_1` would never have matched either.
3. **The Song Structure table was unplannable.** It gave each section's `end_bar` as the
   bar its end time resolves to, which is the *next* section's first bar: `intro 1-8,
   verse_1 8-23, chorus_1 23-38, outro 38-46` on a 45-bar song. Plan bars are inclusive, so
   a plan copying the table failed validation with three overlaps and `outro` beyond bar
   45; the model's `intro 1-7` was the only consistent reading of the table. Before:
   a structure-copied plan → 4 errors; now → none.

Separately, the probe called `HeuristicValidator.validate` and printed `unanswered_high_cues`
but did not fail on placeholder text or an unplanned section.

### Fixed

- `context.py`: a section's `end_bar` is the bar before the one its end time resolves to
  (inclusive, contiguous; the last ends on the song's last bar). Probe song: `intro 1-7,
  verse_1 8-22, chorus_1 23-37, outro 38-45`. A section shorter than a bar is still
  reported as collapsed.
- `heuristic_validator.py`: keyed by `section_id`; an unplanned song section is an
  **error** naming each with its bars; a section's start or end bar differing from the
  structure is an **error**; a `reasoning` or `overall_strategy` under 20 characters or
  four words is an **error** (`MIN_REASONING_CHARACTERS`). A section shorter than a bar
  (sharing its start bar with the next) is not required, since planning both would overlap.
  The evaluation report's `validate_plan_structure` uses the same validator, so a recorded
  plan with empty reasons now reports those errors too.
- `moment_cues.unanswered_high_cues`: a HIGH cue whose section is not planned is counted
  (`section 'chorus_1' is not planned, so its HIGH lyric moment cue 'chorus-light' …`).
- Replay now: 3 validator errors (intro placeholder reasoning; `verse_1`, `chorus_1`,
  `outro` unplanned with their bars; placeholder strategy), one unanswered HIGH cue, exit 1.

### Why the model answered like that (request vs production)

Same request shape as production: `AsyncAgentRunner` (planner is `CONVERSATIONAL`) joins
developer + system into one system prompt with `\n\n`; the provider's `_split_messages`
does the same for the probe's developer, system, user list. Same `effort` (high) and
`max_tokens` (50,000) from the spec; production also passes `timeout_seconds` and the
spec's fallback flag, which change nothing on an enforced call. No `thinking` parameter is
sent; on Opus 5.5 that is adaptive thinking. `reasoning_tokens=0` is a reporting artifact:
`_extract_token_usage` does not split thinking out of `output_tokens`. The response JSON is
860 characters (a few hundred tokens) of 1,218 output tokens, so some thinking likely ran,
briefly; whether it did is not observable from the log.

Defects in what the model read (`msg_user` rendered from the probe 2 request):
- Template library: all templates on one line (Jinja `trim_blocks` ate the newline after
  `{% endif %}`).
- `### Section Planning Directives` heading rendered with nothing under it.
- Song palette arc, motif continuity and focal arc dumped as Python dicts.
- The prompt ended at "Bar Numbering" saying "Plan should cover bar 1 through bar 45",
  with no list of the sections to return; the table it pointed to overlapped.
- Schema descriptions carried docstring noise: a `>>> PlanTransition(...)` doctest and a
  Python-name `Attributes:` list (`SMOOTH_INTERPOLATION`) for `TransitionStrategy`.
- The synthetic song read as a fixture ("Test Song" by "Test Artist", every section
  `MED`, one generic macro note), which may have invited a token answer.

Best-supported explanation: the request never stated the deliverable concretely (every
section, over these bars), its bar table contradicted the validator, and nothing in the
loop rejected a one-section placeholder plan, so a minimal schema-valid answer cost the
model nothing. Hypotheses only another live request can test: that the closing section
list and inclusive table alone produce a full plan; that the fixture-like song contributed;
that adaptive thinking at `high` ran little or none here.

### Changed for the next request

- `planner/user.j2`: one template per line; the directives heading only when there are
  objectives; palette arc, motif continuity and focal arc as readable lines; the plan's
  first requirement is "one entry for each row of the Song Structure table"; bar numbering
  says inclusive; the prompt now ends with `## Return`: each section id with its bars, in
  order, and a request for real reasons and a strategy. Pinned by
  `TestPlannerUserPromptRendering` (rendered from production `build_planner_variables`).
- `transition.py`: `PlanTransition` docstring is one line; `TransitionStrategy` describes
  its wire values. Claude schema 10,941 → 10,297 bytes; still 6 unions / 60 nodes; OpenAI
  40 / 7 / 166. `response_schema_hash` `50a67e62…` → `e09b6057…`.
- Probe: the synthetic song has a title, artist, mood arc, section objectives, an energy
  arc (`LOW`, `MED`, `PEAK`, `RELEASE`) and notes; it runs the production post-provider
  path; prints a per-section table (song bars, plan bars, intent set, parts, events,
  reasoning) and each lyric cue's answer; fails, saying why, on an unplanned section,
  placeholder text, any production validator error, or an unanswered HIGH cue.

## Verification (this tree, fresh)

| Command | Result |
|---|---|
| `uv run pytest tests -q --no-cov` | 6765 passed, 30 skipped, 24 xfailed (after the probe 2 round) |
| `uv run ruff check .` | All checks passed |
| `uv run ruff format --check .` | 1296 files already formatted |
| `uv run mypy .` | no issues in 649 source files |
| `probe_planner.py` (dry run) | enforced, 53,793 request bytes, exit 0 |
| `probe_planner.py --replay probe_response.json` | 3 validator errors, 1 unanswered HIGH cue, exit 1 |
| `pytest tests/regression/test_mh_intent_parity.py` | 2 passed, 24 xfailed |
| `… --runxfail` | 24 failed (target assertions, as at `10f3ac49`), 2 passed |
| `pytest tests/regression/test_mh_pins.py` | 45 passed |

`make validate` was not run (reserved for the integrator).

## Review items 1-14

| # | Item | Done |
|---|---|---|
| 1 | Typeless nullable enums | First typed `["string","null"]` (refused live by Claude); now plain string enums with a sentinel member; guard tests; re-pinned 6 / 60 |
| 2 | Selector policy deleted | Restored and mapped onto `intensity` / `color`; tests restored and extended |
| 3 | Pairing as a model error | Removed from the model; repaired (drop when the value is missing, clear a stray one) |
| 4 | Edge cues dropped | Snapped to the section's nearest beat; out-of-section and out-of-bar events clamped; no-grid binding kept; dropped only when the section has no beat |
| 5 | Unrealised cue feedback | Refinement prompt says how to fix it; HIGH cue unanswered → advisory that re-plans while a round remains, never a failure; judge penalises it |
| 6 | Prompts biased to null | Rewritten (above), pinned by tests |
| 7 | Enforcement stated as fact | "sent as an enforced format; live compile pending the probe" in the test comment, `context/current-state.md`, `docs/overview.md`, `context/architecture/multi-agent-planning.md` |
| 8 | Segment ids lost | `PlanPart.label`, timing labels as above, byte proof with labels |
| 9 | Diagnostic called never-rendered fields a regression | Split |
| 10 | Probe | Retries off, production effort, exit codes, repair count |
| 11 | Event cue id not stripped | Stripped, blank → null |
| 12 | Duplicate / conflicting events | One per kind and beat, recorded |
| 13 | Coarse lengths | Nine steps |
| 14 | Coarse split | Five steps (old default 0.5 → HALF; W0 fixture 0.25 → QUARTER) |

## For the integrator and the owner

1. The fixed schema is unverified live: one further request will be sent by the
   integrator with `probe_planner.py --live`. OpenAI's strict mode accepts plain typed
   string enums (the form every other registered schema already uses).
2. The advisory re-plan can cost one extra planner call per run when a high-emphasis cue
   is left unanswered (never more than `max_iterations` allows).
3. Lengths and splits remain categories (finer now); code owns the exact durations.
4. `context/current-state.md` got one corrected sentence; the rest of the closeout is the
   integrator's.

## Second review (APPROVE with fixes), done

| # | Item | Done |
|---|---|---|
| 1 | Advisory could consume the judge's rounds | Resends at most once per run (`IterationContext.advisory_sent`); test with a planner ignoring the advice twice |
| 2 | No sense of proportion | Proportion paragraph and fit-the-section wording in the planner pack; busy-not-responsive penalty in the judge pack; both pinned |
| 3 | Same-beat tie-break | Cue-bound first, then unrepaired, then first; tested |
| 4 | Advisory text | "an accent that suits its emphasis and visual hint" |
| 5 | Quantisation and defaults | Rows marked "same range, quantised to steps"; old default 0.5 → HALF, W0 fixture 0.25 → QUARTER |
| 6 | Typos | Judge "name the section and the cue"; overview "Its schema is…" |
