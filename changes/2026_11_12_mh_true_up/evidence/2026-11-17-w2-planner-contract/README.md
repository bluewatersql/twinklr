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
`twinklr-mh-true-up`, branch `feat/mh-true-up-p3`, from HEAD `10f3ac49`; uncommitted (the
integrator commits). Plan of record: [song-intent rendering](../../plan/song-intent-rendering.md),
task W2, with the owner's ruling that nothing the planner can express today is dropped.
No provider call, no xLights, no owner data. Where the plan's sketch and the W2 brief
differ, the brief was followed; each difference is listed under
[Differences from the plan's sketch](#differences-from-the-plans-sketch).

W2 reshapes the contract only. It renders no intent: every plan renders the bytes it
rendered at `10f3ac49` (proof below).

## The contract (`agents/sequencer/moving_heads/models.py`)

One response model, `ChoreographyPlan`, replaced in place. No legacy normalisers, no
second model, no switch.

```
ChoreographyPlan{sections: [PlanSection] (>=1), overall_strategy: str}
  (+ repairs: [PlanRepair], code-owned, not in the response schema; see Repair)
PlanSection{section_id, start_bar, end_bar, section_role: str|null, energy_level: 0-100|null,
  parts: [PlanPart{start_bar, template_id, preset_id: str|null, modifiers: [{key, value}], reasoning}] (1-3),
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
  length: BEAT|HALF_BAR|BAR|TWO_BARS|FOUR_BARS|EIGHT_BARS,
  curve: <CurveLibrary, 41 values>, split: EARLY|EVEN|LATE,
  channels: [ChannelTransition{channel: pan|tilt|dimmer|shutter|color|gobo,
                               strategy: snap|smooth|crossfade|fade_via_black|sequence}] (0-6)}
```

- **Null means "as the template is authored"** for intensity, colour and gobo; empty
  lists, `variation` NONE and `density` BALANCED are the neutral values.
  `PlanSection.set_intent_fields()` names the fields a section set away from neutral.
- **Nullable enums** are `Literal[..., None]`: one `enum` that includes null, no union
  (measured below).
- **In-model rules (context-free only):** bar order and 1-indexing; parts start at the
  section's start, are strictly ordered by `start_bar` and start inside the section;
  1-3 parts; an event carries `color` exactly when its action is `color` and `gobo`
  exactly when it is `gobo`; moment cue ids unique and not blank; at most one ENTRY and
  one EXIT; each transition channel at most once.
- **Parts.** A part plays until the next part starts. `flatten_section` turns a section
  of several parts into sections `<id>|A`, `|B`, `|C` (ids derived in code) carrying the
  section's intent, the events on their own bars, every moment cue, the ENTRY on the first
  part and the EXIT on the last. The renderer, the report and the vision judge use it.
- **Saved plans in the old shape** are refused by name (`load_plan`): a plan whose
  sections carry `section_name`, `template_id` or `segments` raises "this moving-head plan
  was saved in the planner contract before 2026-11-17 ... To write it again, <remedy>".
  There is no reader for the old shape.

### Differences from the plan's sketch

| Sketch / brief | Implemented | Why |
|---|---|---|
| `entry: Transition\|null, exit: Transition\|null` | `transitions: [PlanTransition{edge: ENTRY\|EXIT, ...}]`, at most one of each; `section.entry` / `section.exit` read them | The pair, measured, is 7 unions / **68 nodes**: exactly Claude's node limit, no margin. The brief names hoisting the transition so it is referenced once as the first restructuring; it keeps the full range (0 or 1 entry, 0 or 1 exit) at 5 / 57. |
| per-channel strategy "in categorical form" | `channels: [{channel, strategy}]` (0-6, each channel once) | Six nullable fields as an object cost 74 nodes (over the limit); the list says the same thing (any subset of the six channels, each with one of the five strategies) at 57. |
| `modifiers` on the section | `modifiers` on each **part** | The old contract had them on the section *and* on each segment. Per part keeps segment modifiers; section modifiers of an unsegmented section are the one part's; a segmented section's section-level modifiers were discarded by the old flattener and are expressed by giving every part the same entries. |
| Upper-case action, colour and mode spellings | The existing vocabularies keep their own spellings: shutter actions and `ColorPreset`/`GoboPattern`/`CurveLibrary`/`TransitionMode`/`TransitionStrategy` values lower-case, palette roles `PALETTE_<ROLE>`; new categories (length, split, edge, variation, density) upper-case | Every old value is accepted under its old spelling; `PlanColor`'s named colours are exactly the `ColorPreset` values (tested). |
| `section_role`, `energy_level` | kept nullable | The old fields were nullable; dropping null would narrow them. Cost: 2 unions. |
| `overall_strategy` | required (no default) | The old default came from a legacy normaliser, removed. |

## Measured schema size (pinned in `tests/unit/agents/test_structured_outputs.py`)

Measured with the project's `claude_json_schema` / `claude_schema_size` and
`strict_schema_stats`:

| | Claude unions (limit 16) | Claude nodes (limit 68) | OpenAI properties | depth | enum values |
|---|---|---|---|---|---|
| Old contract (`10f3ac49`) | 25 | 126 | 55 | 7 | 94 |
| **W2 contract** | **5** | **57** | **39** | **7** | **161** |
| Alternative: `entry`/`exit` pair, channel list | 7 | 68 | — | — | — |
| Alternative: pair, channels as an object | 7 | 74 | — | — | — |
| Alternative: W2 with `type: ["string","null"]` on the 5 nullable enums | 10 | 57 | — | — | — |

`mh_planner` moved to `_CLAUDE_COMPILED_SPECS`: on Claude the provider now sends the schema
as `output_config.format` (enforced; `tests/unit/agents/providers/test_anthropic.py::
test_moving_head_plan_is_sent_as_an_enforced_format`). The oversize-schema provider tests
now use `MacroPlan` (8 / 83, still over). The five unions are the nullable strings and
integer: `section_role`, `energy_level`, `preset_id`, `moment_cue_id`, `motif_id`.
Response-schema hash: `0a4757a7…5e9043` (was `a76326c7…8683a9`).

The node proxy ignores enum cardinality, so one live request is still the proof that Claude
compiles it: the probe below.

## Field mapping, old contract (`10f3ac49`) → W2, as implemented

Marks: **kept**; **reshaped, same range**; **new**. There is no narrower row; the two
quantised rows are flagged for the owner below.

| Old field | New field | Mark | Notes |
|---|---|---|---|
| `ChoreographyPlan.sections` | `sections` | kept | |
| `ChoreographyPlan.overall_strategy` | `overall_strategy` | kept | Now required (no normaliser default) |
| `PlanSection.section_name` | `section_id` | reshaped, same range | Renamed; it already held the unique section id |
| `start_bar`, `end_bar` | same | kept | |
| `section_role` (str\|null) | same | kept | |
| `energy_level` (0-100\|null) | same | kept | |
| `template_id` XOR `segments` (1-3 `PlanSegment{segment_id, start_bar, end_bar, template_id, preset_id, modifiers, reasoning}`) | `parts` (1-3 `PlanPart{start_bar, template_id, preset_id, modifiers, reasoning}`) | reshaped, same range | One part = unsegmented. Segments had to be contiguous and cover the section, so a part's end is the next part's start. `segment_id` is derived (`A`, `B`, `C`): the section timing mark of a split section is `<id>\|A` etc. (an old plan's own segment words such as `pickup` are no longer a label; the plan's brief directs derived ids) |
| `preset_id` (section or segment, free string) | `PlanPart.preset_id` (free string\|null) | kept | Admission still decides validity; a `--template-dir` preset of any name stays choosable |
| `modifiers` (section and segment) | `PlanPart.modifiers` | reshaped, same range | See the differences table |
| `reasoning` (section and segment) | `PlanSection.reasoning`, `PlanPart.reasoning` | kept | |
| `intensity` (required, 5 values) | `intensity` (5 values or null) | reshaped, same range | null added: as authored |
| `color_intent` (`PALETTE_ROLE` + 5 roles, or `EXPLICIT` + 14 presets) | `color` (5 `PALETTE_*` + 14 presets, or null) | reshaped, same range | Both arms in one enum (tested equal to `PaletteRole` and `ColorPreset`) |
| `shutter_events[]` (`bar`, `beat`, `pattern`: open, closed, strobe_fast/medium/slow, pulse; `moment_cue_id`) | `events[]` with `action` of the same six values | reshaped, same range | |
| `gobo_events[]` (`bar`, `beat`, `pattern`: 13 `GoboPattern`; `moment_cue_id`) | `events[]` with `action: gobo`, `gobo` | reshaped, same range | |
| `moment_cues[{cue_id}]` | `moment_cues[cue_id]` | reshaped, same range | Strip and non-blank kept; unique |
| `transition_in` (`TransitionHint` or null) | `transitions[edge=ENTRY]` (0-1) | reshaped, same range | `mode` same 5 values; `curve` same `CurveLibrary`; `per_channel_overrides` (6 nullable channels × 5 strategies) → `channels` list, same range. `duration_bars` (0-8) → `length` and `fade_out_ratio` (0-1) → `split`: see the quantised rows |
| `transition_out` | `transitions[edge=EXIT]` (0-1) | reshaped, same range | As `transition_in`, with its own length (not shared) |
| `TransitionHint.duration_bars` (float 0-8) | `PlanTransition.length` (BEAT, HALF_BAR, BAR, TWO_BARS, FOUR_BARS, EIGHT_BARS) | reshaped, same range (quantised) | The categories span the old range; a fractional length such as 1.5 bars is not expressible. As the brief and the plan's integrator revision specify |
| `TransitionHint.fade_out_ratio` (float 0-1) | `PlanTransition.split` (EARLY, EVEN, LATE) | reshaped, same range (quantised) | As the brief specifies ("replaces the numeric fade_out_ratio as a category"). The plan's integrator revision still lists this one "awaiting the owner's word" |
| — | `gobo` (section) | new | |
| — | `action: hit` | new | Magnitude later from the cue's emphasis (W6) |
| — | `action: color` with `color` | new | |
| — | `mode: blackout` | new | Added to `TransitionMode` |
| — | `motif_id`, `variation`, `density` | new | Former T3 fields |
| — | null for intensity, colour, gobo | new | As authored |

Removed with their callers (rule 9; `git grep` shows no other importer, config or doc
reader): `PlanSegment`, `ColorIntent`/`ColorIntentKind`/`PaletteRoleColorIntent`/
`ExplicitColorIntent`, `ShutterEvent`, `GoboEvent`, `MomentCueReference`,
`flatten_plan_segment`, every `_normalize_legacy_*` validator and `legacy_intent_omitted`
(models and `transition.py`); `TransitionHint` and `ChannelTransitionOverrides`
(`sequencer/models/transition.py`, replaced by `PlanTransition`/`ChannelTransition`);
`sequencer/moving_heads/libraries/shutter.py` (`ShutterPattern`, whose values now live in
`EventAction`; it had no other importer); `lyric_moment_cue_errors` (replaced by repair);
the selector's intent policy (`SelectorConfig.intensity_cutoffs`, `accent_roles`,
`neutral_roles`, `SelectionTrace.unresolved_intent_fields`, `_intensity`,
`_palette_role`), which only fed intent the selector no longer sets. Historical documents
that name them are left as history.

## Repair rules (`moment_cues.bind_lyric_moment_cues`)

The normaliser runs on every planner response before validation. **Structural** problems
still raise and go through the existing refinement loop: a section id naming no song
section, a display name naming several (`chorus` for `chorus_1, chorus_2`), a song section
used twice; then the heuristic validator: a template not offered, a section beyond the
song, overlapping sections. Everything else is **one item**, dropped or adjusted and
recorded as a `PlanRepair{section_id, item, action: dropped|adjusted|recorded, reason}`:

| Item | Repair |
|---|---|
| A `moment_cues` id naming no lyric cue, a cue of another section, or a cue whose timestamp lies outside its own section | reference dropped |
| An event bound to such a cue (or, with no beat grid, any bound event) | unbound, keeps its own bar and beat (adjusted) |
| An event bound to a usable cue of the section that `moment_cues` does not list | the reference is added (adjusted) |
| An event bound to a usable cue | moved to the cue's timestamp snapped to the nearest beat (as before, for every action now) |
| An event whose cue snaps outside the section | dropped |
| An unbound event outside the section's bars, or on a beat its bar does not have | dropped |
| A referenced cue that no event lands on | recorded (nothing synthesised) |

The run never fails for one item. Repairs replace any earlier list on the plan (a
normalised plan normalises to itself). They reach:
- the **judge**, in the plan JSON it is shown (`repairs`), explained in its developer prompt;
- the **next refinement prompt**: the controller's new `plan_repairs` hook stores
  `repair.describe()` lines on `IterationContext.plan_repairs`, and `user_refinement.j2`
  lists them under "What Deterministic Repair Changed in Your Last Plan";
- the **render trace**: `render_record["plan_repairs"]`, only when there are any (so other
  traces keep their keys), and the `eval-report` render block;
- **regeneration** keeps the kept sections' repairs and takes the re-planned section's own.

Tested with the provider mocked:
`test_orchestrator.py::...::test_a_repaired_item_reaches_the_judge_and_the_next_planning_prompt`
(an unknown cue and an out-of-section event are repaired, the run continues to the judge,
the next planner prompt lists both repairs, the approved plan has none), next to the
existing structural-refusal loop test.

The action/field pairing of an event is an in-model rule, as the brief specifies: an
unpaired event fails model validation and goes through the runner's schema-repair attempt,
not deterministic repair (Claude's grammar does not enforce the pairing).

## Consumers

| Consumer | Change |
|---|---|
| Renderer (`sequencer/moving_heads/pipeline.py`) | Iterates `flatten_section`; template and preset from the one part; the per-section diagnostic now names the set fields: "section 's1': the planner's song intent (intensity, color) is not rendered yet, a known regression being fixed under changes/2026_11_12_mh_true_up/plan/song-intent-rendering.md; the template renders as authored", emitted only when a field is set; `plan_repairs` in the record |
| Identity (`identity.py`) | Hashes the plan dump with canonical template ids per part; the `legacy_intent_omitted` flag is gone |
| `check_regeneration_base`, regeneration merge (`stage.py`) | Per part; repairs merged |
| Deterministic selector | One part per section with its effective variant; all intent neutral |
| Three-arm experiment (`three_arm.py`) | Admission check per part; the "every schema-v2 intent field" check removed |
| Evaluation report (`generator.py`, `models.py`, `render.py`, `rerender.py`, `collect.py`) | `SectionReport.song_intent` (`SongIntentReport`: every field, events and transitions one line each, `not_rendered`); markdown "Song intent (as planned)" block; `RenderSummary.plan_repairs`; old-shape checkpoints refused by name |
| Vision evaluation | The judge's per-section intent line carries every field, templates per part and `not_rendered_yet` |
| Live plan load (`cli/main.py`) | Old-shape records refused by name: "run `twinklr inject` to re-plan the whole song into <sequence>" |
| Show stage | The macro palette/focal-role diagnostic and docstring reworded as a known regression naming the plan |
| Planner context (`context.py`) | Each macro section now carries `palette_colors` (hex and name of every stop of its palette), shown under "Section palettes" in the planner and judge prompts; nothing removed from the song context |
| Prompts (planner, judge) | Edited in place for parts and song intent: what each field means as creative intent, palette roles resolving through the song's palette, accents on lyric cues by emphasis and on musical moments, transitions by mode, motif variation, density, null = as authored, rig-dependent availability with repair and report |

## User-visible changes and re-keying

- **Every song plans again once.** The planner cache key hashes the response schema
  (`spec_prompt_hash` → `response_schema_hash`): the schema hash changed
  (`a76326c7…` → `0a4757a7…`) and the prompt-pack hashes changed with it
  (`cfb07167…` → `261030a7…`), so no old plan is reused; no manual cache-version bump is
  needed (`test_the_response_schema_re_keys_the_plan_cache`). The first `run`/`show`/
  `inject` per song is a paid planning call.
- **Old checkpoints** (`checkpoints/plans/final.json` written before this change) are
  refused by `eval-report` by name; re-run the command that planned them. The two
  historical checkpoints under `evaluations/` are old-shape and stay as history.
- **Old live plans** (`.twinklr-live-plans.json`) are refused by `regenerate` by name before
  any planner; run `twinklr inject` again.
- **On Claude** the plan is now schema-enforced (it was prompt-only).
- Renders, timing tracks and sidecars are byte-identical; render **fingerprints** change
  (the plan dump they hash changed). The trace's per-section intent diagnostic changes
  wording and appears only for sections that set intent.

## Byte proof

Scripts are in the session scratchpad (session-local, not committed), `<w2>` =
`/private/tmp/claude-501/-Users-ondeck-work-github-twinklr/9cfb5b66-fff4-47db-adcb-766b50dc61e9/scratchpad/w2`.
Harness: `<w2>/matrix_w2.py` (from the C1.4 matrix), run once on
`git archive 10f3ac49` and once on this tree, each building its plans in its own contract
(`<w2>/run_matrix.sh`, compared by `<w2>/tools/compare_w2.py`).
360 configurations (8 rigs incl. the zoom pilot rig, 3 fixture timings, 5 grids incl. 3/4
and silent edges, 3 policies), three plans each:

- **A**: every admitted family, no presets;
- **B**: the families reversed, alternating `narrow` / `slow` presets;
- **C**: two sections, each split into two parts/segments (ids A, B), every song intent set
  (DRAMATIC, an explicit and a palette-role colour, a strobe and a gobo event, a crossfade
  entry), so the parts flattening and the intent-ignoring path are both covered.

Result: 1,080 renders, 20,250 compared leaves. **Identical**: frames, returned segments,
the gate's admissions, the normalised render record and trace, `.xsq`, `.xtiming`,
`.xmap` of every render. **Different, by design only**: the render fingerprint, the raw
record and raw trace file (they carry the fingerprint, and plan C's reworded intent
diagnostic, normalised to its presence per section). The deterministic selector's plans
(seeds 1-3, 8 sections) render byte-identical frames, segments, `.xsq`, `.xtiming` and
`.xmap` in both trees (`<w2>/selector_bytes.py`).

Pins (`tests/regression/test_mh_pins.py`): all 44 frame hashes and both `.xsq` hashes
unchanged; the 44 render fingerprints were re-recorded (the docstring says so), and the
combined-show golden's moving-head fingerprint
(`tests/golden/fixtures/combined_show_drop.json`, `3be80a97…` → `0389342a…`) likewise;
its effects and trace hashes are unchanged.

Intent parity (`tests/regression/test_mh_intent_parity.py`): only the "Plans and calls"
block was rewritten, plus `overall_strategy=""` on the anchor's plan construction (the
contract no longer defaults it); no assertion, row id or xfail marker changed. Normal run:
2 passed, 24 xfailed. With `--runxfail`: the anchor passes and all 24 rows fail; each fails
on the same assertion source line with a byte-identical message as at `10f3ac49`
(`<w2>/tools/parity_compare.py`).

## Live probe (prepared, not run)

`probe_planner.py` (this folder) builds the real rendered planner pack (developer, system,
user) for a synthetic song: the unit tests' four-section, 90 s, 120 BPM audio profile and
macro plan (palette `core.christmas_traditional`), three synthetic lyric moment cues
(MED, HIGH, LOW), the family catalog. It sends **one**
`AnthropicProvider.generate_json_async` call to `claude-opus-5-5` with the
`ChoreographyPlan` response model and no prompt-only fallback, then validates, normalises
and checks the plan and prints the song intent per section and any repairs.

```bash
# Dry run (default): builds the exact request, prints sizes, sends nothing.
uv run python changes/2026_11_12_mh_true_up/evidence/2026-11-17-w2-planner-contract/probe_planner.py
# The one paid request (owner-authorized, minimum only; ANTHROPIC_API_KEY set):
uv run python changes/2026_11_12_mh_true_up/evidence/2026-11-17-w2-planner-contract/probe_planner.py --live --out probe_result.json
```

Dry-run output on this tree: schema 5 unions / 57 nodes, 10,357 bytes; messages: developer
23,129, system 4,626, user 7,854 characters; `schema_enforced True`; request 48,549 bytes;
effort `low` (`--effort` to change), `max_tokens` 50,000 (the planner spec's).

## Verification (this tree, fresh)

| Command | Result |
|---|---|
| `uv run pytest tests -q --no-cov` | 6663 passed, 30 skipped, 24 xfailed |
| `uv run ruff check packages tests scripts` | All checks passed |
| `uv run ruff format --check packages tests scripts` | 1290 files already formatted |
| `uv run mypy packages/twinklr` | no issues in 644 source files |
| `pytest tests/regression/test_mh_intent_parity.py` | 2 passed, 24 xfailed |
| `pytest tests/regression/test_mh_intent_parity.py --runxfail` | 24 failed (target assertions, as at `10f3ac49`), 2 passed |
| `pytest tests/regression/test_mh_pins.py` | 45 passed |

`make validate` was not run (the brief reserves it for the integrator).

## For the integrator and the owner

1. **OpenAI strict mode, unverified.** The default provider is OpenAI. The five nullable
   enums are `{"enum": [..., null]}` with no `type` key, as the brief directs (no union on
   Claude). No registered schema had that form before, and OpenAI's acceptance of a
   type-less enum cannot be checked offline. If OpenAI rejects it, the measured fallback
   is to add `"type": ["string", "null"]` to those five nodes: 10 unions / 57 nodes, still
   within Claude's limits.
2. **Quantised transition numbers.** `length` and `split` are categories as the brief
   specifies; a 1.5-bar or 0.4-split transition is no longer expressible. The plan's
   integrator revision records `fade_out_ratio` → split as awaiting the owner's word.
3. **Derived part ids** replace planner-chosen segment ids in section timing labels.
4. The paid probe is ready (above); run it after review and log it with the owner's
   authorization.
5. `context/current-state.md` got a one-line correction (its "schema-v2 sections" sentence
   was made false); the rest of the closeout is the integrator's.
