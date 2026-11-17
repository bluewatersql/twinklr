---
type: evidence
status: complete
area: engineering
change: 2026_11_12_mh_true_up
created: 2026-11-17
updated: 2026-11-17
---

# W3 and W4 — the rig offer, and section colour and gobo rendered

**Provenance.** Implemented by an executor agent on 2026-11-17 in the worktree
`twinklr-mh-true-up`, branch `feat/mh-true-up-p3`, from `9deb95df`. Uncommitted; the
integrator commits. Plan of record: [song-intent rendering](../../plan/song-intent-rendering.md),
tasks W3 and W4, under the owner's ruling that song intent is rendered, never cut. No
provider call, no network, no xLights, nothing under `~/xlights`, `data/` or
`artifacts/`; every rig, song and palette here is synthetic or the repository's catalog.
`make validate` was not run (reserved for the integrator); the commands it wraps were run
one by one (§ Verification).

This is the first task in which song intent becomes visible light. **The owner has not
seen it**: the W4 view is pending (§ What to look for).

## What was built

| Area | Change |
|---|---|
| `sequencer/moving_heads/song_intent.py` (new) | The one resolver: palette stop policy, the fixed role table, `HeadWheels` (a head's offered states), `RigOffer` and `rig_offer`, `resolve_section_look`, `repair_rig_intent`, `offer_for_prompt`, `describe_look` |
| `config/fixtures/state_tags.py` | `nearest_tagged_color` / `tagged_gobo` (the W1 lookups over a head's tagged states), `oklch`, the lightness-discounted grade (`ColorMatch.graded_distance`); W1's `rig_color_offer`, `rig_gobo_offer`, `rig_strobe_offer` and their types removed, superseded by `RigOffer` (rule 9) |
| `sequencer/moving_heads/pipeline.py` | `TemplateAdmission.offer` (and `record()` for the checkpoint); the gate computes the offer and widens each template's entry-dip bound with the offered wheel states; `RenderingPipeline(palettes=...)`; per section the resolved look is compiled in (`held_states`), boundary dips or the previous state kept (`_boundary_change`); trace `section_looks` and `palettes`; colour and section gobo removed from the "not rendered" diagnostic |
| `compile/template_compiler.py` | `compile_template(held_states=...)`: per fixture, wheel states held over every cue before overlays |
| `identity.py` | `RENDERER_REVISION` 2 → 3; the fingerprint hashes the palettes of the sections that resolve a palette role through one |
| Planner (`context.py`, `orchestrator.py`, `stage.py`, prompts) | `MovingHeadPlanningContext.rig_offer` (from the gate) and `palettes`; prompt section "What This Rig Can Show"; the cache key hashes the offer; `normalize_plan` = cue binding then `repair_rig_intent`; developer and judge prompts say what a rig repair means |
| `deterministic_selector.py` | `SelectorAdmission.offer`; the selector's palette-role colours go through `repair_rig_intent` |
| `rendering_stage.py`, `show_stages.py`, `cli/main.py` | `run` and `show` pass the macro plan's section palettes to the render (`render_palettes`); `inject` records them with the live plan; `regenerate` renders kept sections through the recorded ones |
| Reporting (`collect.py`, `rerender.py`, `generator.py`, `models.py`, `render.py`, `vision_evaluation.py`) | The checkpoint's offer and palettes read back and re-rendered with; a palettes mismatch is named; the report's `played` lines; "not rendered" lists exclude colour and gobo |
| Tests | `tests/unit/sequencer/moving_heads/test_song_intent.py` (new, 25), `.../test_section_look_render.py` (new, 9), the intent pin, offer/cache/normaliser/prompt/stage/CLI/selector/report tests; the config ledger repointed (§ Tests) |
| Docs | User guide (the rig offer; how colour and gobo reach the lights; tags), pipeline guide, overview, developer guide, QA runbook, README, glossary, product overview, multi-agent planning, `context/current-state.md`, the plan's W0 table |

## W3 — the rig offer

### Model

`TemplateAdmission.offer: RigOffer`, computed by `admit_templates` (the pre-planning gate,
one projection; `SelectorAdmission.from_gate` carries the same object):

| Field | What |
|---|---|
| `heads` | Per head: whether it has a colour / gobo wheel, and its **offered** colour states (`hex`) and gobo states (`pattern`): tagged, on a wheel whose every state has a known `settle_ms` (corrected in the review fix round: first written per state, which let an authored state without a settle cost admission) |
| `color(c)` / `preset_colors()` | For any colour (every `ColorPreset`, any palette stop): `faithful` (every colour-wheel head `exact`/`close`), `approximate` (every one shows it, some only `approximate`), `partial` (some cannot: they keep their authored colour, named in `missing`), `unavailable`; each head's state and fit |
| `gobos` | Each `GoboPattern`: `all` / `some` / `none` of the gobo-wheel heads, with states and the heads missing it |
| `strobes` | Each strobe speed: `all` / `some` / `none` of the heads with a shutter |
| `hit` | Heads with a dimmer axis: `all` / `some` / `none` |
| `wheel_change_ms`, `wheel_change_beats` | The longest dark + turn + settle of any head into any offered state, frame-rounded as the transaction pass times it (close latency, plus the slowest extinguishing shutter settle where only the shutter extinguishes, then the state's settle, at least one frame); in beats at the song's median beat |

Per section, the palette roles resolved through that section's macro palette are a pure
function of the offer and the palette (`offer_for_prompt`), computed where the macro plan
exists (planning), because the gate runs before the macro planner.

### Policy decisions

1. **Mixed rigs** (as recommended): a colour or gobo plays on every head that can show
   it at least `approximate`; a head that cannot, or has no such wheel, keeps its
   authored look, and the offer names it. `partial` is offered and flagged in the prompt
   ("only some heads show … not MH3").
2. **Grading discounts lightness** (state_tags change, tested): `fit` is graded on the
   Oklab difference to the slot *dimmed* to the level nearest the request
   (`min over 0 < s ≤ 1 of |request − s·slot|`; a dimmer scales linear RGB, which scales
   every Oklab coordinate alike). A darker shade of a slot's colour grades as that colour;
   a lighter or more saturated request keeps its difference. Selection is unchanged
   (hue first). Measured on the catalog's 80 stops × three wheels (white/red/blue/green,
   eight-slot, open/red/amber/pink/blue/green): 42 of 127 `approximate` grades become
   `close` (39) or `exact` (3); nothing moves the other way. W1 pins that changed:
   `warm_white` → white `exact` (was `close`) on all five wheels; orange → CTO `close`
   (was `approximate`); peach `#FFCCBC` → white `close` (was `approximate`); `ColorMatch`
   gains `graded_distance`. Why: the offer told the planner "approximately" for palette
   greens and reds a wheel shows well.
3. **Approximations are not repairs.** The offer tells the planner up front, and the
   trace records what played; listing them as repairs would ask the planner to "re-plan"
   what is only the wheel's nearest slot.

### Entry-dip bound (`pipeline.py`, `_entry_dips`)

A section's colour or gobo can turn the wheel at any section entry, so each head's offered
states join both the states the predecessor may hold and every rung's entry states.
**What changes:** on a rig with tagged states, each template's *reported* worst-case dip
(`entry_dips`, logged and in the checkpoint) grows by the slowest offered settle less what
the bound already counted. Admission does not change: an offered state always has a
settle, so it can never leave a rung without a bound. Measured in the byte matrix
(§ Byte proof), tagged family rig, 45 configurations: every family's bound +40 ms (the
star gobo's 160 ms against 120 ms already counted; `masked_wheel_flick` +20 or +40), the
reported beats +1 in 54 of 270 (template, configuration) cases, the fixture named
changing in 30; admitted templates and exclusions identical everywhere. Untagged rigs:
identical (the offered sets are empty). On owner-like timings (close latency 20 ms,
every wheel state settling in 150 ms, four heads, 16 bars at 120 and at 78 BPM; scratch
`w34/gate_dips.py`) tagging changes nothing at the gate: the same six families admitted,
the same exclusions, every dip the same (360–400 ms, one beat), because the bound
already counted a 150 ms settle. **The dark-dip requirement refuses no family on the
owner's kind of rig**: the gate does not model the boundary dip at all (a dip that does
not fit keeps the previous colour instead), and the offer's wheel change there is
180 ms, inside half a beat at 78 BPM (384.6 ms) and at 120 BPM (250 ms).

### What the planner reads

Rendered from production variables for `tagged_family_rig` (white, red, blue; open, dots,
star) and the test macro plan (`core.christmas_traditional` on every section), 120 BPM:

```
## What This Rig Can Show

Deterministic code turns your `color` and `gobo` into the rig's wheel colours and
patterns; a head that cannot show a choice keeps its template's own look there.
- **Colours shown faithfully**: red, blue, white, warm_white, cool_white
- **Colours shown approximately**, as the nearest wheel colour: magenta as red, cyan as blue, orange as red, purple as blue, amber as red, uv as blue
- **Colours this rig cannot show** (they keep the template's colour): green, yellow, lime
- **Palette roles, by section** (the stop each role takes and the wheel colour it lands on):
  - `intro`, `verse_1`, `chorus_1`, `outro` (`core.christmas_traditional`): PALETTE_PRIMARY #E53935 → red; PALETTE_ACCENT #43A047 → not shown; PALETTE_WARM #E53935 → red; PALETTE_COOL #43A047 → not shown; PALETTE_NEUTRAL #FFFFFF → white
- **Gobos**: on every head: open, stars, dots; not shown: circles, triangles, diamonds, clouds, prism, shatter, flame, water, foliage, abstract
- **Strobe speeds**: none tagged
- **Hit** (a dimmer accent): every head
- **A wheel change** takes 160 ms dark (about 0.4 beat): the heads go dark to turn a wheel. A colour or gobo change between two sections the heads play straight through costs a dark dip of up to half a beat just before the new section, so hold a colour across sections that flow into each other and change it where the music turns.
```

An untagged rig reads instead that its colour wheel (gobo wheel) "says no colour it shows
(no state is tagged), so no colour is offered". Sections sharing a palette share one line;
without a macro plan the line says "(no macro palette: the fixed colours)". The
proportion and song-responsiveness guidance is untouched; the developer prompt's "What
the rig and the song can hold" points at this section, and the judge is told that a
colour or gobo repaired to `as_authored` because the rig cannot show it is the rig's
limit, not an ignored palette. Pinned by `TestPlannerUserPromptRendering`.

**Cache key.** The planner cache key hashes `rig_offer.model_dump(mode="json")` (heads,
offered states, gobos, strobes, hit, wheel change, median beat; no free text), and the
prompt packs changed: **every song plans again once** (paid), and a re-tag of the rig
re-plans.

### Repair rules (`repair_rig_intent`, run by `normalize_plan` after cue binding)

| Item | Repair |
|---|---|
| Section colour no head shows (`unavailable`, including an untagged rig) | Cleared to `as_authored`; `adjusted`, with asked colour, its hex and source, and why (no colour wheel / no `hex` tags / nothing like it) |
| Section colour only some heads show (`partial`) | Kept; `recorded`, naming the heads that play it and those that keep their authored look |
| Section gobo no head has / some have | Cleared (`adjusted`) / kept and `recorded` |
| Colour event whose colour no head shows; gobo event whose pattern no head has | Event `dropped` (nothing left to play) |
| Colour or gobo event only some heads show | Kept, `recorded` |
| Colour a head shows only approximately | Not a repair (see above) |

"Repaired to the nearest offered alternative when one is approximate or better" is the
per-head resolution itself: each head plays its nearest offered state unless that is a
`hue_mismatch`. The run never fails for one item; repairs reach the trace, the
`eval-report`, the judge and the next refinement prompt. The deterministic selector's
palette-role colours go through the same function with no palettes (it reads no macro
plan), i.e. the fixed role table, as its render without a macro plan plays them.

## W4 — section colour and section gobo rendered

### Resolver and stop policy (`requested_color`, `palette_role_color`)

| Colour | Resolves to |
|---|---|
| Named colour (`red` … `uv`) | `COLOR_PRESET_HEX` (W1's canonical values) |
| `PALETTE_PRIMARY` | The section's palette's first stop |
| `PALETTE_ACCENT` | Its second stop (the first in a one-stop palette) |
| `PALETTE_WARM` / `PALETTE_COOL` | The stop with a hue (OKLCh chroma ≥ 0.04) nearest 55° (orange) / 230° (between cyan and blue); chosen, not measured |
| `PALETTE_NEUTRAL` | The least saturated stop |
| A role without a macro palette for the section (or WARM/COOL in a palette of whites) | The fixed table: PRIMARY red, ACCENT magenta, WARM amber, COOL cyan, NEUTRAL white (the deleted renderer's table); the trace's `source` says `fixed table (<colour>: <reason>)` |

Then each head plays `nearest_tagged_color` over its offered states; gobo: `tagged_gobo`.
**One resolver for `run` and `show`**: both pass the macro plan's palettes
(`section_palettes`) to `RenderingPipeline(palettes=...)`. That satisfies the W9 parity row
`show_palette_color` (PRIMARY under `show` on `spec.cosmic_night` → its first stop
`#0D47A1` → blue), so its xfail was removed too. The focal-role part of W9 was not done.

### Application in the renderer

The resolved state replaces the held `color`/`gobo` of every cue of the section's steps
and their component presets (`compile_template(held_states=...)`, applied per fixture
before overlays). **Overlays:** a template's own overlay keeps its state over its window,
and its cues then return to the *section* colour, not the authored one. Why: the overlay
is the template's accent on top of the section's look; returning to the authored colour
would undo the section colour for the rest of every cycle. And a head whose overlay state
equals the section colour plays it throughout, unmasked (the existing `apply_overlay`
rule). Tested (`test_an_overlay_keeps_its_state_and_returns_to_the_section_colour`).

### When the wheel turns (always dark)

1. **A section entered through a dark window** (its heads reposition into it): the turn
   rides that window. `worst_case_entry_ms` already counts the entry wheel states' settle,
   so the window may grow by up to one beat where the turn is slower than the rest.
2. **A boundary the heads play lit through** (today's entry is `skipped`) where song
   intent changes a wheel (this section's colour or gobo, or the previous section's):
   the tail of the previous section's last cue is commanded dark on its own path
   (`_dark_over_spans`: the head keeps moving as authored, so no repositioning is needed),
   the wheel turns once the head is optically dark, settles, and the head reveals on the
   section's first frame exactly as before. The dark lead is `wheel_change_ms`
   (frame-rounded darkness + max(settle, one frame)); it must be at most half the beat
   before the boundary and fit inside the previous cue, and the entry must then still
   play as authored (`_plays_as_authored`, which also times the shutter). Otherwise the
   head **keeps the previous section's colour** into the section (recorded with the
   reason). A change that is not song intent's (two as-authored sections) is left as it
   was; where the colour does not change, nothing is added.

A first design cut the previous cue short instead; the transaction then had to re-aim a
moving head after the turn, which on a 120 BPM grid with a 40 ms close latency did not fit
half a beat, so nearly every lit boundary kept the previous colour. Darkening on the cue's
own path needs only the darkness, turn and settle.

**Timing, owner-like timings** (close and open latency 20 ms, every wheel state settle
150 ms, darkness through the dimmer; `mirror_wings` red → `mirror_wings` blue, every head
`skipped` at the boundary; scratch `w34/tempo_examples.py`):

| | 120 BPM | 78 BPM |
|---|---|---|
| Beat, half beat | 500 ms, 250 ms | 769.2 ms, 384.6 ms |
| Wheel change (offer) | 20 + 160 = 180 ms (0.36 beat) | 180 ms (0.23 beat) |
| Section start T (first frame) | 8020 ms | 12320 ms |
| Dimmer commanded 0 | 7840 ms (T − 180) | 12140 ms |
| Optically dark, wheel commanded red → blue | 7860 ms (T − 160) | 12160 ms |
| Wheel settled | 8010 ms | 12310 ms |
| Reveal, lit in blue | 8020 ms (T, as before) | 12320 ms |
| Frames dark that were lit | 9 (7840–8000) | 9 (12140–12300) |

In words: the light goes dark 180 ms before the downbeat that starts the section, the
wheel turns in the dark, and the head comes back on that downbeat in the new colour,
having kept moving. On the owner's rig the darkness is the dimmer, which the xLights
preview shows.

`as_authored` colour and gobo render today's bytes exactly (§ Byte proof).

### Trace, diagnostics, report

- Trace `section_looks` (only when a section sets a colour or gobo, or a boundary dips):
  per section `color` (asked, hex, source, status, each head's state and fit,
  `kept_authored`), `gobo` (asked, availability, heads, `kept_authored`) and `boundaries`
  (per head: wheels from → to, and `dark_dip {from_ms, lead_ms, turn_ms}` or
  `kept_previous {reason}`). Trace and checkpoint `palettes` when a section resolves a
  palette role through one.
- The per-section "not rendered yet" diagnostic no longer lists colour or section gobo;
  it still lists intensity, shutter and gobo events and their cue binding, entry
  transition (regressions) and hit and colour events, moment cues, exit transition,
  motif, variation, density, modifiers (never rendered). The `show` diagnostic now names
  only the focal role.
- `eval-report`: `song_intent.played` per section (e.g. `colour PALETTE_COOL (#2979FF,
  palette 'core.rgb_primary' stop 3): blue (approximate) on MH1; MH2 keep their authored
  colour`), shown in the markdown; `not_rendered` and the vision judge's
  `not_rendered_yet` exclude colour and gobo.

## Fingerprint, revision, cache

- **`RENDERER_REVISION` 2 → 3**: a plan that sets a colour or gobo renders differently
  for an unchanged plan and rig. Every render fingerprint changes.
- The fingerprint also hashes `palettes` (only for sections whose colour is a palette
  role, only when there are any): the macro palette now affects bytes. The plan dump was
  already hashed; the rig (tags included) already was.
- `checkpoint_record`: `admission` now includes `offer`; `palettes` (and
  `inputs.palettes`) when present; `eval-report` re-renders with them and names a
  `section palettes` mismatch. A checkpoint written before this change lacks
  `admission.offer` and is reported malformed (re-run the command); its fingerprint would
  not match anyway (revision 3).
- **`check_regeneration_base` coverage:** the rig, tags included, is already in the live
  plan identity (`rig_sha256`), so a re-tagged rig refuses a regeneration. The palettes
  are not known at the gate (the macro planner runs later), so instead `inject` records
  the section palettes with the live plan, and `regenerate` renders every kept section
  through the recorded palette (the re-planned section takes this run's) —
  `render_palettes`. A live-plan record without `palettes` (written by W2-era code) is
  refused as unreadable, telling the user to re-inject.
- **Pins:** all 44 frame hashes and both `.xsq` hashes unchanged; their 44 + 2
  fingerprints re-recorded (script verified the frames before rewriting each); the
  combined-show golden's moving-head fingerprint `b2583195…` → `bf6be5e6…`, its effects
  and trace hashes unchanged.
- **Planner cache:** re-keyed (offer and prompt packs): every song plans again once.

## Parity rows turned green

`tests/regression/test_mh_intent_parity.py`, xfail markers removed, no assertion changed:
`color_explicit_blue`, `color_palette_primary`, `color_palette_accent`,
`color_palette_warm`, `color_palette_cool` (W4) and `show_palette_color` (W9, see above).
The suite: 8 passed, 18 xfailed (was 2 passed, 24 xfailed). `--runxfail`: the 18 still
fail on their own target assertions.

## New pin

`INTENT_PIN` in `tests/regression/test_mh_pins.py`
(`test_section_colour_and_gobo_on_a_tagged_rig_are_pinned`): steady grid,
`tagged_family_rig`, four sections — `mirror_wings` red; `finite_snap_hold` blue +
stars; `masked_wheel_flick` `PALETTE_PRIMARY` through `spec.cosmic_night` (blue,
approximate; the flick overlay on top); `mirror_wings` as authored (white again, with
dark dips on the two heads that play that boundary lit). Fingerprint `8cf74893…`, frames
`ad91f4f2…`, `.xsq` `9968e9a4…`.

## Byte proof (unchanged cases)

Harness: `w34/matrix_w34.py` (the W2 matrix, plus a tagged family rig, and the record
normalised for the keys W4 adds by design: `section_looks`, `palettes`,
`renderer_revision`), run on `git archive 9deb95df` and on this tree; 405 configurations
(9 rigs × 3 fixture timings × 5 grids × 3 policies) × 3 plans = 1,215 renders. Plans A and
B are as authored; plan C sets every intent, including an explicit and a palette-role
colour (no macro palette given, so the fixed table), on every rig.

Result (22,815 leaves compared; scratch `w34/compare_w34.py`):

- **Identical in every render of plans A and B (810, every rig, the tagged one
  included) and of plan C on the eight untagged rigs (360):** frames, returned segments,
  normalised record and trace, `.xsq`, `.xtiming`, `.xmap`. Neither a neutral plan nor
  an untagged rig moves a byte; colour intent on an untagged rig plays as authored.
- **Different by design only:** every fingerprint and raw record/trace (revision 3;
  `section_looks`); on the tagged rig, plan C's frames, segments, `.xsq`, record and
  trace (45 configurations: its colours now render), and the gate's reported entry dips
  (bound, beats, fixture: above). Admitted templates and exclusions: identical in all
  405. No render errored on either tree.

## Tests

- New: `test_song_intent.py` (stop policy, fixed table, offered states, mixed-rig colour
  statuses, gobo/strobe/hit, wheel change time incl. shutter darkness and unknown latency,
  section look per head, repair rules, prompt grouping); `test_section_look_render.py`
  (dip before a lit boundary: every wheel change inside a dark window covering close
  latency before and settle after, darkness differs from neutral only in the dip, at most
  half a beat; no dip without a change; previous colour kept when the dip does not fit;
  as-authored on a tagged rig = untagged bytes; section gobo; mixed rig; overlay return;
  palettes in identity; gate dip widening with equal admission); the intent pin;
  `test_the_fit_grades_the_slot_at_the_dimmer_level_nearest_the_request`; cache key,
  normaliser, prompt variables, prompt rendering (tagged and untagged), stage hands the
  offer, rendering stage records and re-reads palettes, regeneration palettes (unit and
  CLI), selector repair.
- Ledger (`tests/config_effects_registry.py`): `hex` and `pattern` repointed to
  `test_state_tag_changes_what_a_section_plays` (the tagged state plays, frames change);
  `strobe` and `offer` stay identity-only (`test_state_tag_changes_identity_not_output`),
  notes updated (strobe: offered, no frame until W6).
- Changed for intended behaviour: the W1 grade table (decision 2), the unrendered
  diagnostic and report tests (colour no longer listed), the combined-show diagnostic
  filter (focal role), constructions of `TemplateAdmission`/`SelectorAdmission`/
  `RecordedRender` (new required fields).

## What the owner should look for (W4 view; PENDING-OWNER)

Render a song with a tagged rig (the `profile_tags.txt` snippet filled in) and a plan with
section colours:

1. Each section holds its colour on every head that can show it; the colour follows the
   section's palette role (PRIMARY the palette's first colour, ACCENT its second).
2. **Look change to judge:** at a boundary the heads play straight through, a colour
   change now costs a short blackout just before the downbeat (about 180 ms on the owner's
   timings; at most half a beat). Is that acceptable, too often, or should colour changes
   be kept to boundaries that already enter dark?
3. A head whose wheel lacks the colour keeps the template's colour (white): acceptable on
   a mixed rig?
4. `masked_wheel_flick` returns to the section colour after its flick, not to white.
5. Approximations: palette colours a wheel lacks show as the nearest slot (e.g. a palette
   green on a white/red/blue wheel is not shown at all; magenta shows red).

## Limits and open points

- (Superseded by the review fix round, item 4: overlay masks are now checked against
  the offered settles at the gate, and the render falls back to the authored state.)
- The dip needs the dark lead inside the previous cue; a shorter last cue keeps the
  previous colour (recorded).
- Colour and gobo **events** are repaired against the offer but not rendered (W7);
  strobe tags are offered, not rendered (W6).
- WARM/COOL hue references (55°, 230°) and the fixed table are chosen, not measured.
- On the owner's rig nothing is tagged yet, so every colour is repaired to `as_authored`
  and renders as today until the rig is tagged (the owner's layout read for tag
  suggestions stays owner-gated).

## Verification (this tree, fresh)

Run after the last code edit, 2026-11-17:

| Command | Result |
|---|---|
| `uv run pytest tests -q --no-cov` | 6814 passed, 30 skipped, 18 xfailed (was 6765 / 30 / 24 at `9deb95df`) |
| `uv run pytest tests/regression/test_mh_pins.py -q --no-cov` | 46 passed (45 re-recorded fingerprints with frames/`.xsq` unchanged, plus the intent pin) |
| `uv run pytest tests/regression/test_mh_intent_parity.py -q --no-cov` | 8 passed, 18 xfailed; `--runxfail`: 18 failed, every one an `AssertionError` on its target |
| `uv run ruff check .` | All checks passed |
| `uv run ruff format --check .` | 1299 files already formatted |
| `uv run mypy .` | No issues in 650 source files |
| Byte matrix (`w34/run_matrix.sh`, base `9deb95df`) | As § Byte proof |

Scratch (session-local, not committed):
`/private/tmp/claude-501/-Users-ondeck-work-github-twinklr/9cfb5b66-fff4-47db-adcb-766b50dc61e9/scratchpad/w34/`
(`matrix_w34.py`, `compare_w34.py`, `run_matrix.sh`, `tempo_examples.py`,
`gate_dips.py`, `render_prompt.py`, `two_sections.py`, `rerecord_pins.py`,
`intent_pin.py`, `golden_fp.py`).

## Review fix round (2026-11-17, on `e611164f`)

The independent review of `e611164f` (frame-by-frame over about 150 renders, no physical
violation found) returned REQUEST CHANGES, items 1–12. All were done; uncommitted, no
`make validate`, no provider call. Where this section and the text above differ, this
section is current.

| # | Item | Done |
|---|---|---|
| 1 | Tagging cost admission (an authored state without `settle_ms` lost every bound) | `HeadWheels.from_profile` offers a wheel only when **every** state of it has a settle (`unsettled` names the rest); `tag_guidance` names each missing settle with a paste-ready placeholder (refused if pasted unfilled); the CLI note says "or wheel states without a settle_ms". Tests: a partly settled, tagged rig admits exactly what the same rig admits untagged, with equal dips and nothing offered for that wheel; the guidance test |
| 2 | Template dark phases were left out of the offer | **I dropped them in W3 without saying so; that was a scope cut I should have reported.** Now `RigOffer.templates[template].variants[base\|preset] = DarkPhases(cycle_beats, heads)`: per admitted variant and fixture, the dark windows of its first cycle in beats from the cycle start (gaps between cues from visibility envelopes and overlay masks, frames the cues command dark; the entry dip stays in `entry_dips`), from the gate's bar-1 compile. `DarkPhases.first_window(head, beats)` is the query the repair uses and W6/W7 can use. Tests: `masked_wheel_flick`'s two masks (beats 2–3 and 5–6 of 8) on every head, `mirror_wings` none |
| 3 | A colour change that could not dip kept the previous colour for the whole section | Rule now (a) dip before the boundary within half a beat; (b) else turn in the section's first dark window long enough (`_dark_windows`: a dark phase or overlay mask, a gap, a dark span), the head playing the previous colour until then; for an overlay family the section is recompiled at the old colour so its mask opens, and the turn is validated (in a gap with `entry_feasible`; inside a cue by construction: dark from the window's start, turned after the darkness latency, settled before the window ends); (c) else keep the previous colour. (b) and (c) are recorded per head with times (`boundaries[].deferred {turn_ms, waited_ms, late}` / `kept_previous {reason}`), and the plan repair (`rig_repair._boundary_repairs`, run with the beat grid in `normalize_plan`) records for the planner every change into a section whose template has no dark window long enough in its first half (c), or whose first one lies past half the section (late b). The repair cannot know whether the heads play straight into the section (that needs the render), so it says "where the heads play straight into it" and over-reports sections that enter dark (seen on Dance Jams below). Tests at 170 BPM: `masked_wheel_flick` turns in its first mask on all four heads (no darkness added), `mirror_wings` keeps red, recorded; repair prediction test |
| 4 | A slow offered state under overlay masks: cues forced dark, or a refusal after paid planning | Gate: each overlay template's admitted variants are compiled at bar 1 holding every head's slowest offered state on the overlay wheel, then the next slower settle down, until the placement plans; slower states go to `TemplateOffer.excluded` (per fixture and wheel), which the prompt lists ("Not with these templates"), the repair (`RigOffer.for_templates`) and the render resolution use, and the entry dips respect. Render safety net: a head whose section cues with the held state do not plan where the authored ones do plays the authored state in that section (`kept_authored_unplayable`, recorded, a warning); never a refusal for this cause. Tests: a green settling in 470 ms under `masked_wheel_flick` at 120 BPM is excluded for that template only; without the gate's result, every head falls back to the authored colour and the render does not refuse under `on_unplayable: error` |
| 5 | Trace, report and prompt claimed colours the frames did not show; the prompt contradicted itself | The render moves each head that does not play the asked state from the section's start out of `heads` into `deferred {state, from_ms}`, `kept_previous` or `kept_authored_unplayable` (`_played_record`); a per-section warning counts them; `describe_look` and the report's `played` lines say so ("MH2 turns to blue at 9020 ms", "MH3 keeps the previous colour red"). The prompt states the rule by tempo: where the change fits half a beat, the dip; where it does not, the wait for the first dark moment (naming the templates that have one) or no change |
| 6 | Palette roles not in the palette | WARM / COOL resolve only to a stop with a hue within 90° of 55° / 230°, NEUTRAL only to a white (chroma below 0.04); otherwise the role is not in that palette: the prompt says "not in this palette", a plan that picks it is repaired to `PALETTE_PRIMARY` (recorded), and the render plays PRIMARY's stop (never a fixed-table colour under a macro palette). Over the 19 catalog palettes: no WARM in 5 (`core.ice_neon`, `core.mono_cool`, `core.uv_party`, `spec.cosmic_night`, `spec.futuristic_teal`), no COOL in 4 (`core.gold_warm`, `core.magma`, `core.mono_warm`, `spec.gritty_embers`), no NEUTRAL in 2 (`core.magma`, `core.rainbow_bright`). The prompt marks a role landing on the same wheel colour as an earlier one ("(same wheel colour as PALETTE_PRIMARY)") and suggests contrast through a named colour, intensity or gobo. Tested over every catalog palette on the four wheels (w/r/b/g; w/r/b; open/red/amber/pink/blue/green; eight-slot) |
| 7 | The lightness discount over-promised | A request darker than 0.8 of the slot's relative luminance is graded on the plain ΔE (the slot plays at the template's level): olive → yellow, maroon → red, grey → white are `approximate`, no longer `exact`. W1 expectations re-judged: orange → CTO `approximate` (was `close` in W4), peach → white `approximate`; `warm_white` → white stays `exact` (0.88 of white's luminance), the palette green `#00E676` stays `close` (0.81). The prompt now says once that a wheel shows a colour's hue at the section's brightness (`intensity` is the control) |
| 8 | Dip vs existing darkness | The dip starts no earlier than it must: where the previous cue already commands darkness for the whole lead (a show's rest, a dark phase), nothing is darkened and `dark_dip.added_ms` is 0; otherwise the dip darkens only what is lit. Test: a dark span over the last beat before the boundary adds no darkness |
| 9 | Import cycle | `song_intent.py` no longer imports the planner package at run time (it reads plan values as strings, `PlannedLook` protocol); the plan-mutating repair moved to `agents/sequencer/moving_heads/rig_repair.py`. Test: each of `song_intent`, `rig_repair`, `pipeline`, `context` imports first in a fresh interpreter |
| 10 | Lost coverage, weak render tests | Mixed-rig strobe all/some/missing and `#000000` unavailable restored (`test_song_intent.py`); a shutter-only-darkness rig dip test; the overlay test at 40 ms close latency; the dark-window assertion now counts shutter settle where only the shutter extinguishes |
| 11 | Cache key hashed the palette id only | It hashes each section's resolved stops (`palettes`); test: an edit of a catalog palette's stops re-keys |
| 12 | Flick equal to the section colour | Noted in the user guide and here: under `masked_wheel_flick`, a head whose flick colour equals the section's colour shows no flick (its overlay has nothing to turn to) |

### Consequences

- **`RENDERER_REVISION` 3 → 4** (deferral, overlay fallback, a missing role playing PRIMARY
  change bytes for an unchanged plan and rig). Every fingerprint re-recorded; every frame
  and `.xsq` hash unchanged, `INTENT_PIN`'s included (its boundaries all dip at 120 BPM).
  Golden moving-head fingerprint `bf6be5e6…` → `5fd51634…`. **New pin** `FAST_INTENT_PIN`
  (170 BPM, owner-like timings: a change deferred into `masked_wheel_flick`'s mask, a
  change kept over `mirror_wings`).
- The planner cache re-keys again (palette stops, offer with dark phases and exclusions,
  prompt packs).
- Byte matrix against `9deb95df` re-run on this tree: the same classification as § Byte
  proof (as-authored plans on every rig and plan C on every untagged rig identical in
  frames, segments, normalised record and trace, `.xsq`, `.xtiming`, `.xmap`; only the
  tagged rig's plan C and gate dips differ; admission identical in all 405). Against the
  first W4 round, no frame and no gate result of the matrix changed (its fastest grid,
  340 ms beats, still fits the tagged family rig's 160 ms change in half a beat).
- Parity: 8 passed, 18 xfailed; `--runxfail` 18 failed, all `AssertionError` on their
  targets.

### Verification (fix round, after the last code edit)

| Command | Result |
|---|---|
| `uv run pytest tests -q --no-cov` | 6860 passed, 30 skipped, 18 xfailed |
| `uv run pytest tests/regression -q --no-cov` | 58 passed, 18 xfailed (47 pins) |
| `uv run ruff check .` | All checks passed |
| `uv run ruff format --check .` | 1301 files already formatted |
| `uv run mypy .` | No issues in 651 source files |
| Byte matrix vs `9deb95df` | As above |

### Item 3 on a real fast grid: `Dance Jams Final Audio.mp3`

Owner-authorised for this change (implementation brief, Approvals; recorded by the
coordinator). Read in place at `/Users/ondeck/work/github/twinklr/data/music/` (the brief
named `data/songs/`, where no such file exists; the file of that name is under
`data/music/`). Offline: local DSP analysis only, every enhancement off (metadata,
lyrics, phonemes, AcoustID, MusicBrainz, online lyrics, WhisperX), the analysis cache
under the scratchpad; no LLM or provider stage. Script `w34/dance_jams.py`. Rig: the
tagged four-head family rig with owner-like wheel timings (close latency 20 ms, every
colour and gobo state settling in 150 ms: a 180 ms change). Plan: hand-built over the
song's 13 DSP sections (bars from the detected grid), cycling through the admitted
families, colours alternating red and blue.

| | |
|---|---|
| Grid | 129.2 BPM, 4/4, 135 bars, 542 beats; beats 348 / 464 / 569 ms (min / median / max); 258.5 s; the analysis warned "Low downbeat phase confidence: 0.00" |
| Admitted | `finite_snap_hold`, `fly_in_cascade`, `fly_out_cascade`, `masked_wheel_flick`, `mirror_wings`, `target_orbit`; `zoom_wave` excluded (no zoom axis) |
| Dark phases published | cascades: several windows of 1–6 beats per cycle; `masked_wheel_flick`: beats 2–3 and 5–6; `finite_snap_hold`, `mirror_wings`, `target_orbit`: none; no exclusions |

At the owner-like 180 ms change (fits half the median beat, 232 ms, and the half beat
before each boundary that dipped): of 12 boundaries, the changes into the cascades and the flick were played
in the gaps between cues (their entries plan as authored through a dark gap, so no
boundary record), those into `finite_snap_hold` rode its entry window, and **6 heads at 4
boundaries** (into `mirror_wings` and `target_orbit`, entered lit) **dipped 180 ms before
the section**. Nothing deferred or kept; 0 repairs. **This song's tempo does not need
item 3's deferral at the owner's timings.**

To exercise it on this real grid, the same run with a slower wheel (every state settling
in 300 ms: a 320 ms change, more than every half beat): the same 6 heads at the same 4
boundaries **kept the previous colour** (no dark window in `mirror_wings` /
`target_orbit`), each recorded in the trace with its reason; the changes into the
cascades, the flick and `finite_snap_hold` still played (gaps, entry windows). The plan
repair recorded **6 colour changes** for the planner: the 4 that kept the previous
colour, plus 2 into `finite_snap_hold` that in fact played through its entry window (the
repair cannot see which boundaries are entered dark; it over-reports, never
under-reports). No deferral into a dark window occurred on this plan: the sections with
dark phases (cascades, flick) were entered through gaps, which turn the wheel anyway.
Acceptance as stated (colour changes play wherever a dark window exists; every one that
cannot is recorded and fed back as a repair): met on this song, with the over-report
noted.

## Second review follow-ups (2026-11-17, on `9d607f45`)

The second review approved with one MEDIUM and six LOW follow-ups. Each is fixed in the
same tree as W5's intensity rendering (shaping inside `compile_section` is untouched).

| # | Finding | Fix |
|---|---|---|
| 1 (MEDIUM) | The boundary repair over-reported for templates that always enter dark (`finite_snap_hold` at 170 BPM: 3 false reports of 3), and the repair's "late" (start past half the section's beats) disagreed with the render's (turn time past the middle) | The gate checks every ordered pair of admitted templates (`pipeline._dark_entries`): each pair of their admitted variants, the predecessor compiled from bar 1 and the successor from each bar after it up to the predecessor's longest cycle, through `_enters_lit`, the same entry test `_boundary_change` makes (a back-to-back, non-substitutable previous cue whose next cues play as authored with the wheels held). It publishes `RigOffer.dark_entries` (successor → predecessor → the heads that always enter dark); the repair leaves those heads out. Skipped on a rig that offers no wheel state. `song_intent.is_late` (the dark window opens past half the section, one frame of tolerance) is now the one definition, used by both render sites and the repair. The repair also carries a predicted kept colour into the next boundary |
| 2 | A dip added darkness existing darkness could replace, the half-beat bound tested the whole lead, and `added_ms` reported the lead | `pipeline._dip_span`: of the places the added darkness can start (the full lead before the boundary, or the end of any dark run the previous cue commands, so the dip rides it), the one adding the fewest lit frames; the half-beat bound applies to that added darkness; `dark_dip.added_ms` is it and `from_ms` is where the darkness the turn rides begins |
| 3 | A template-excluded state was reported as "no head's colour wheel shows anything like it"; a multi-part section took the union of its parts' exclusions | The repair judges each part on its own template's offer (`rig_repair._parts`, `_judge`); events on the part they fall in. A state the rig shows but a template excludes names the template: "template 'masked_wheel_flick' cannot turn the color wheel to it and back in time: its overlay masks are too short for that state's settle". A state some parts show is kept and recorded ("plays in the parts on …; not in those on … (…)") |
| 4 | The prompt's tempo rule used the median beat | `offer_for_prompt(..., half_beats)` adds `dip_boundaries` (`fit`, `of`, `shortest_half_beat_ms`) from half the beat before each section boundary (`MovingHeadPlanningContext._boundary_half_beats`, over `song_structure()`'s bars); the prompt says "It fits half the beat before N of this song's M section boundaries" when some do and some do not, and falls back to the median beat without a grid |
| 5 | `FAST_INTENT_PIN` docstring said green | Says white, and why no boundary is recorded there (it enters dark) |
| 6 | "Plays PRIMARY" was untrue where PRIMARY is not shown | Repair reason, prompt, user guide and current state now say the role is changed to `PALETTE_PRIMARY`, which then plays or not as any colour |
| 7 | The repair used the rig-wide wheel change time | `HeadWheels.change_ms` (each head's longest change into an offered state); the repair judges and names each head on its own |

### Item 1 against the render

Synthetic owner-like rig (close latency 20 ms, every state settling 150 ms: 180 ms), 170
BPM, four sections alternating red / blue over one admitted family, the gate's offer
(scratch `repair_vs_render.py`):

| Family | Sections of 1 bar | 2 bars | 4 bars |
|---|---|---|---|
| `finite_snap_hold`, `fly_in_cascade`, `fly_out_cascade` | 0 repairs / render enters dark | same | same (was 3 false reports for `finite_snap_hold`) |
| `masked_wheel_flick` | 0 / 3 deferrals, none late (window at beat 2 of 4, the middle) | 0 / 3 deferrals | 0 / 3 deferrals |
| `mirror_wings`, `target_orbit` | s2, s4 / kept at s2, s4 | same | same (was s2, s3, s4: s3 changed nothing, s2 having kept) |

Gate cost: 2.25 → 2.37 s (16 bars), 9.11 → 9.19 s (64 bars) on the 7-family catalog.

`Dance Jams Final Audio.mp3` (owner-authorized, offline, read in place, outputs under the
scratchpad), every state settling 300 ms (a 320 ms change): the render kept the previous
colour on 6 heads at s5, s6, s11, s12, as before. The repair now records **4** colour
changes, s5 and s11 (MH2, MH3: the heads the render kept) and s6 and s12 (MH1, MH4,
where the render kept one of them); **none into `finite_snap_hold`** (was 6, 2 of them
false). At 150 ms settle: 6 dips, 0 repairs, unchanged.

### Item 2: bytes

| Case (scratch `dip_spans.py`) | Before | After |
|---|---|---|
| 120 BPM, no span | dip, 180 added | same, same frames |
| 120 BPM, span over the boundary | dip, `added_ms` 0, from 7840 | same frames; `from_ms` 7500 (where the darkness begins) |
| 120 BPM, span ending 120 ms before | dip, `added_ms` 180 (wrong) | `added_ms` 140; same frames |
| 170 BPM, span ending 120 ms before | kept the previous colour | dip adding 120 ms (frames change) |
| 170 BPM, span straddling (−160, +200) | deferred 20 ms into the section | dip adding 20 ms (frames change) |
| 170 BPM, span covering (−400, +400) | deferred 20 ms into the section | turned in the darkness before the boundary, nothing added (frames change) |

Bytes change only where a show's rest (a dark span) meets a lit colour change whose
lead does not fit half a beat, or whose lead it covers. `RENDERER_REVISION` is 6.

- Byte matrix (405 configs × 3 plans, scratch `run_matrix.sh` on an export of
  `9d607f45` and on this tree): admission, frames, segments, `.xsq`, `.xtiming`,
  `.xmap`, normalized record and trace identical in all 1215 renders; only the
  fingerprint, the raw record and the raw trace differ (the revision string).
- Pins: every frame and `.xsq` hash unchanged; the 49 fingerprints re-recorded
  (revision 6). The combined-show golden: effects and trace hashes unchanged; its
  render fingerprint re-recorded.

### Tests added

`test_rig_repair.py`: a template that always enters dark is not recorded and each head is
judged on its own change; a template exclusion names the template; a multi-part section
judges exclusions per part. `test_section_look_render.py`: at 170 BPM a dip rides a dark
span (ends before, straddles, covers: 120 / 20 / 0 ms added, darkness changed only
inside the lead); the gate publishes `finite_snap_hold` after itself for every head and
not `mirror_wings`, the repair records none and the render enters dark; an untagged rig
publishes none. `test_song_intent.py`: `dip_boundaries`, `is_late`. `test_prompts.py`:
on a variable grid the prompt says 2 of 3 boundaries.

### Verification (second review follow-ups)

`pytest tests -q --no-cov`: 6938 passed, 30 skipped, 13 xfailed. Parity
(`test_mh_intent_parity.py`): 13 passed, 13 xfailed; with `--runxfail` the 13 targets
fail. Pins (`test_mh_pins.py`): 50 passed. `ruff check .`, `ruff format --check .`,
`mypy .`: clean. No commit, no `make validate`, no provider calls.
