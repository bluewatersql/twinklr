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
  intensity: SLOW|SMOOTH|FAST|DRAMATIC|INTENSE|null,
  color: PALETTE_PRIMARY|PALETTE_ACCENT|PALETTE_WARM|PALETTE_COOL|PALETTE_NEUTRAL
         |red|blue|green|yellow|magenta|cyan|orange|purple|amber|lime|white|warm_white|cool_white|uv|null,
  gobo: open|circles|triangles|stars|diamonds|clouds|prism|shatter|dots|flame|water|foliage|abstract|null,
  moment_cues: [cue_id],
  events: [PlanEvent{bar, beat, moment_cue_id: str|null,
                     action: open|closed|strobe_slow|strobe_medium|strobe_fast|pulse|hit|color|gobo,
                     color: <colour vocabulary>|null, gobo: <gobo vocabulary>|null}],
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

- A null intensity, colour or gobo keeps the template's own look; the prompts ask the
  planner to answer the song and to give a reason for any null (Prompts below).
  `PlanSection.set_intent_fields()` names the fields a section set away from neutral.
- **Nullable enums** are `Literal[..., None]`. The strict-schema builder
  (`schema_utils._normalize_supported_schema`) now types every bare string enum: a
  nullable one is `{"type": ["string", "null"], "enum": [..., null]}`, a non-null one
  `{"type": "string", ...}`, so OpenAI strict mode, which needs a type on every value
  schema, accepts it (review item 1). Each costs one union on Claude.
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
| **W2 after the fix round** | **11** | **60** | **40** | **7** | **166** |

The fix round added one union per typed nullable enum (5: section `intensity`, `color`,
`gobo`; event `color`, `gobo`), and the nullable `label` (1 union, 3 nodes). The finer
length (9) and split (5) enums cost no node. Margin: 5 unions, 8 nodes. The eleven unions:
`section_role`, `energy_level`, `preset_id`, `label`, `moment_cue_id`, `motif_id` and the
five nullable enums. Response-schema hash `d9389872…88be49` (was `a76326c7…8683a9` at
`10f3ac49`). `test_no_registered_strict_schema_has_an_untyped_enum` guards every
registered spec; no other spec's size changed.

`mh_planner` is in `_CLAUDE_COMPILED_SPECS`: by measure it is within the limits and the
provider sends it as `output_config.format`. **Its live compile is pending the probe**
(review item 7; the test comment and `context/current-state.md` say so). The
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
| `intensity` (required, 5 values) | `intensity` (5 values or null) | reshaped, same range | null added |
| `color_intent` (`PALETTE_ROLE` + 5 roles, or `EXPLICIT` + 14 presets) | `color` (5 `PALETTE_*` + 14 presets, or null) | reshaped, same range | Both arms in one enum (tested equal to `PaletteRole` and `ColorPreset`) |
| `shutter_events[]` (`pattern`: 6 values; `moment_cue_id`) | `events[]`, `action` of the same 6 values | reshaped, same range | |
| `gobo_events[]` (`pattern`: 13 `GoboPattern`; `moment_cue_id`) | `events[]`, `action: gobo` + `gobo` | reshaped, same range | |
| `moment_cues[{cue_id}]` | `moment_cues[cue_id]` | reshaped, same range | |
| `transition_in` (`TransitionHint` or null) | `transitions[edge=ENTRY]` | reshaped, same range | Same 5 modes and `CurveLibrary`; `per_channel_overrides` → `channels` list |
| `transition_out` | `transitions[edge=EXIT]` | reshaped, same range | Its own length (not shared) |
| `TransitionHint.duration_bars` (0-8) | `length`: 9 steps, BEAT (¼ bar in 4/4) … EIGHT_BARS, including 1½, 3 and 6 bars | reshaped, same range, quantised to steps | Review item 13: the whole old range in finer steps; a value between steps snaps to the nearest (1.25 bars → BAR or ONE_AND_HALF_BARS); code owns the exact milliseconds |
| `TransitionHint.fade_out_ratio` (0-1) | `split`: QUARTER, THIRD, HALF, TWO_THIRDS, THREE_QUARTERS | reshaped, same range, quantised to steps | Review item 14; a value between steps snaps to the nearest. The old model's default 0.5 is HALF; the W0 parity fixture's 0.25 is QUARTER |
| — | `gobo` (section), `action: hit`, `action: color` + `color`, `mode: blackout`, `motif_id`, `variation`, `density`, null for intensity/colour/gobo | new | |

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

After (Plan Structure):
> **Every section answers the song.** Set `intensity` from its energy target, a
> palette-role `color` from its palette, and an accent (an event) on every high- and
> medium-emphasis lyric moment cue and on the drops and hits. Leave a field null only when
> you can say in `reasoning` why the template's own look already answers this moment. A
> plan whose sections are mostly null ignores the song.

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
boundary, "A field left null needs a reason there.").

**Judge developer.** Before: "Song-intent fields that are null or empty mean 'as the
template is authored'; that is valid, not missing" and "…left as authored where the
template already serves?". After: a null is "schema-valid, but judged in Phase 2 as a
choice that needs a reason"; Musical Synchronization requires a cue-bound event for every
high-emphasis cue and intensity that follows the energy targets; **Penalise** an
unanswered high-emphasis cue (and unanswered medium ones), flat intensity across a clear
energy change, colour that ignores the palette, and mostly-null plans ("cannot score above
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
same way ("from the section's energy (null: the template's own)").

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
  (`spec_prompt_hash` → `response_schema_hash`, `a76326c7…` → `d9389872…`) and the prompt
  packs (`cfb07167…` → `b495d2ec…`); no manual bump is needed
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
`98f85710…`); its effects and trace hashes unchanged.

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
tree: schema 11 / 60, 10,971 bytes; developer 27,715, system 4,890, user 8,342 characters;
`schema_enforced True`; request 54,685 bytes; exit 0.

## Verification (this tree, fresh)

| Command | Result |
|---|---|
| `uv run pytest tests -q --no-cov` | 6754 passed, 30 skipped, 24 xfailed |
| `uv run ruff check .` | All checks passed |
| `uv run ruff format --check .` | 1296 files already formatted |
| `uv run mypy .` | no issues in 649 source files |
| `pytest tests/regression/test_mh_intent_parity.py` | 2 passed, 24 xfailed |
| `… --runxfail` | 24 failed (target assertions, as at `10f3ac49`), 2 passed |
| `pytest tests/regression/test_mh_pins.py` | 45 passed |

`make validate` was not run (reserved for the integrator).

## Review items 1-14

| # | Item | Done |
|---|---|---|
| 1 | Typeless nullable enums | Typed `["string","null"]` by the strict builder; guard test over every registered spec; re-pinned 11 / 60 |
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

1. The OpenAI acceptance of `["string","null"]`-typed enums and Claude's compile of the
   11 / 60 schema are both unverified live; the Claude probe is ready (above). The OpenAI
   form is the one OpenAI documents for nullable fields.
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
