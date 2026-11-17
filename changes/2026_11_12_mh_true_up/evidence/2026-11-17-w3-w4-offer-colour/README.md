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
| `heads` | Per head: whether it has a colour / gobo wheel, and its **offered** colour states (`hex`) and gobo states (`pattern`): tagged, and with a known `settle_ms` (a wheel turns only in the dark, and its settle times the turn; a tagged state without one is not offered) |
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

- **Overlay masks are not re-checked against offered settles at the gate.** An overlay
  returning to a section colour whose state settles slower than the authored base could
  need more than its mask; the gate checks the authored base only. Catalog impact:
  `masked_wheel_flick` (1-beat masks; the offered settles are 120–160 ms) — not hit in
  any test or the matrix; under `on_unplayable: dark` such a cue would be kept dark, under
  `error` the render refuses.
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
