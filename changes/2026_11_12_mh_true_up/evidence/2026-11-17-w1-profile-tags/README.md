---
type: review
status: complete
area: engineering
change: 2026_11_12_mh_true_up
created: 2026-11-17
updated: 2026-11-17
---

# W1: profile meaning tags — 2026-11-17

Task W1 of [song-intent rendering](../../plan/song-intent-rendering.md): a fixture's
physical profile can now say what each wheel and shutter state *is*, so the planner's
colour, gobo and strobe intent has something to resolve to. Worktree
`feat/mh-true-up-p3`, on `af504809`. Nothing committed. No provider, network, xLights
process, `~/xlights`, `data/` or `artifacts/` was used; every profile and layout here is
synthetic. `make validate` was not run (the brief forbids it); the commands it wraps
were run individually (§ Verification).

**No renderer or planner wiring.** Nothing reads a tag yet; W3 (the rig offer) and W4
(section colour and gobo) will. Frames, `.xsq` and every pin are unchanged.

## What was added

| Path | What |
|---|---|
| `packages/twinklr/core/config/fixtures/capabilities.py` | `DiscreteState.hex`, `.pattern`, `.strobe` (optional, left out of dumps when absent); `StrobeSpeed`; `STATE_TAGS` (the one tag each channel kind takes); `FixtureCapabilities._validate_tags` |
| `packages/twinklr/core/config/fixtures/state_tags.py` (new) | The lookup API (`tagged_colors`, `nearest_color_state`, `color_distance`, `gobo_state`, `strobe_state`, `ColorMatch`), the guidance (`tag_guidance`, `rig_tag_guidance`) and the layout derivation (`layout_color_tags`) |
| `packages/twinklr/core/sequencer/moving_heads/libraries/color.py` | `COLOR_PRESET_HEX` (each `ColorPreset`'s canonical colour) and `canonical_hex` (a `#RRGGBB` or a preset name → uppercase `#RRGGBB`) |
| `packages/twinklr/core/formats/xlights/layout/models/rgb_effects.py` | `Model.dmx_color_wheel()` and `DMX_COLOR_WHEEL_SLOTS`: the one reader of a DMX model's colour-wheel slot attributes |
| `packages/twinklr/core/profiling/layout/profiler.py` | Reads the slots through `Model.dmx_color_wheel()` instead of its own loop (same attributes, same 20 slots, same order) |
| `packages/twinklr/cli/main.py` | `twinklr run`/`inject`/`regenerate` print `rig_tag_guidance` before analysis, after the layout check |
| `tests/unit/config/test_mh_state_tags.py` (new) | 155 tests after the review follow-up: model, validation, lookups, guidance, layout derivation, the guide's example, ledger evidence |
| `tests/config_effects_registry.py` | Six ledger paths (three tags × two profile roots) |
| `tests/regression/test_mh_intent_parity.py` | `parity_rig` carries real `hex` tags; its test-side `STATE_HEX` stand-in and RGB nearest-state helper are replaced by `nearest_color_state` (xfail markers untouched) |
| `tests/unit/cli/test_live_injection_command.py` | `twinklr run` prints the paste-ready tags, with a layout proposal |
| `tests/unit/profiling/test_layout_profiler.py` | The profiler still reads colour-wheel slots (guards the moved reader) |
| `docs/user-guide.md` | New "State meaning tags" section and a row in the profile defaults table |
| `context/glossary.md`, `context/current-state.md` | Physical profile entry; one line in the known-regression bullet |

## Model and validation rules

| Tag | On | Value | Stored |
|---|---|---|---|
| `hex` | `color` states | `"#RRGGBB"` (any case) or a `ColorPreset` name | Uppercase `#RRGGBB`; a name becomes its canonical colour |
| `pattern` | `gobo` states | A `GoboPattern` value (`open` included) | The value |
| `strobe` | `shutter` states | `slow`, `medium` or `fast` (the planner's `strobe_slow`/`_medium`/`_fast`) | The value |

Refused when the profile loads (a fixture file names the fixture or `base_config` in
front, as for every profile error):

| Case | Message (abridged) |
|---|---|
| Tag on another kind's state | `discrete.gobo.states.dots.hex: a gobo state takes `pattern`, not `hex`; move the tag to a color state or remove it` |
| Malformed `hex` | `discrete.color.states.red.hex: Value error, 'FF0000' is not a colour: write '#RRGGBB' (six hex digits) or one of red, blue, …, uv` |
| Unknown pattern / speed | Pydantic's enum and literal errors at `discrete.gobo.states.<s>.pattern` / `discrete.shutter.states.<s>.strobe`, listing every allowed value |
| Two shutter states, one speed | `discrete.shutter.states: 'strobe_a' and 'strobe_b' both claim strobe 'fast'; one state per speed: tag one of them with another speed (slow, medium or fast), or remove its tag` |
| `strobe` on the open, closed or an extinguishing state | `discrete.shutter.states.closed.strobe: 'closed' is the shutter's closed_state and an extinguishing shutter state (visibility), which cannot strobe; …` |

Not tags, because the profile already owns the fact: which shutter state is open
(`open_state`), closed (`closed_state`) and dark (`visibility.extinguishing_shutter_states`).

Decisions (reversible; the owner may overrule any):

1. **Preset names are accepted in `hex`, one stored form.** A name resolves to
   `COLOR_PRESET_HEX` when the profile loads and the profile stores and dumps only the
   hex, so `"red"` and `"#FF0000"` are the same profile and fingerprint. Why: it lets the
   guidance suggest a readable, paste-ready value (`"hex": "red"`) and saves a rig
   author looking up hex for the common case; a fixture whose slot is a different red
   writes its own hex. `COLOR_PRESET_HEX` is the deleted renderer's palette-projection
   table (`show_coordination.py` `_PRESET_RGB` at tag `mh-last-with-legacy-renderer`),
   restored as the one canonical value of each preset; W4's "explicit colour → its
   canonical value" is meant to use the same table. The values are chosen, not measured.
2. **Two colour states may share a colour.** A wheel can hold two slots of one colour, or
   an open slot and a white one; both are true descriptions, and a lookup is still
   deterministic (ties by state name). Refusing would force the author to lie.
3. **Two gobo states may share a pattern.** The usual case is a static and a shaking copy
   of one gobo (`star`, `star_shake`); `gobo_state` returns the first by state name.
4. **Strobe speeds are unique per shutter channel.** Two states claiming one speed is a
   labelling mistake: a speed has to name one state for the planner's `STROBE_FAST` to
   mean anything.
5. **A strobe tag cannot sit on the open, closed or an extinguishing state**, since those
   states mean steady lit or dark.
6. **Tags are never recorded in `defaulted`**, because they are never filled.

## Lookup API (what W3/W4 call)

All pure functions of one `FixtureCapabilities`, in
`twinklr.core.config.fixtures.state_tags`:

| Function | Returns |
|---|---|
| `tagged_colors(profile)` | `{state: "#RRGGBB"}` for tagged colour states, by state name; `{}` without a colour channel or tags |
| `nearest_color_state(profile, color)` | `ColorMatch(state, hex, distance, fit)` for the tagged colour state that shows `color` (`#RRGGBB` or a preset name), by the rule below, ties going to the first state name; `None` when no colour state is tagged; `ValueError` for a request that is not a colour |
| `color_distance(a, b)` | Oklab colour difference (ΔE_OK) between two colours |
| `gobo_state(profile, pattern)` | The first gobo state by name tagged with `pattern`, else `None` |
| `strobe_state(profile, speed)` | The shutter state tagged with `speed`, else `None` |

**Colour matching (revised on the coordinator's follow-up, same day; the fit grades, hue cap, canonical purple and amber and the CLI note were revised again after review: § Review follow-up, which supersedes this section where they differ).** The first pass
ranked slots by CIE76 ΔE, which sent a light saturated colour to white (cyan `#00E5FF` →
white on a white/red/blue/green wheel). For a light show that is wrong: a planner asking
for cyan should get blue or green. The rule now, all in OKLCh (`NEUTRAL_CHROMA = 0.04`):

1. A request with a hue (chroma ≥ 0.04) is matched only against tagged slots with a hue,
   ranked by hue angle difference, then chroma difference, then lightness difference.
   White slots are used only when no tagged slot has a hue (`fit =
   "no_chromatic_match_used_neutral"`).
2. A white request (chroma < 0.04: white, warm white, cool white, the palettes' `#F5F1E8`)
   goes to the white slot nearest in Oklab (lightness and tint); on a wheel without one,
   to the nearest slot.
3. Ties by state name. `distance` is ΔE_OK between request and slot (0 same colour, about
   0.02 just noticeable, black to white 1); `fit` is `exact` (distance 0), `approximate`,
   or `no_chromatic_match_used_neutral`.

Why OKLCh rather than CIELCh: Oklab's hue is close to uniform where CIELAB's is not; in
CIELAB pure blue sits at hue 306°, beside purple (328°), while palette blues (`#0D47A1`,
`#2979FF`) sit at 289°. In OKLCh blue is 264° and those blues 260°. Why 0.04: the
presets' whites reach 0.029 (`cool_white`) and the palette catalog's tinted white 0.013,
while its palest tints start at 0.060 (`#B3E5FC`, `#FFCCBC`); saturated wheel colours
are 0.15 and up.

Every preset on three wheels (pinned in `test_every_colour_preset_resolves_by_hue_on_realistic_wheels`):

| Request (OKLCh hue) | white/red/blue/green | 8-slot (w r o y g b m c) | open/red/amber/pink/blue/green |
|---|---|---|---|
| red (29°), blue (264°), green (143°) | exact | exact | exact |
| yellow (110°) | green | yellow | amber |
| magenta (328°) | red | magenta | pink |
| cyan (195°) | green | cyan | green |
| orange (53°) | red | orange | red |
| purple (328°) | red | magenta | pink |
| amber (84°) | red | **yellow** | amber |
| lime (126°) | green | yellow | green |
| white, warm_white, cool_white | white | white | open |
| uv (288°) | blue | blue | blue |

Every stop of every catalog palette (80 stops, 19 palettes) was checked on the three
wheels: a stop with a hue never lands on a white slot, and the whites always do
(`test_no_palette_colour_with_a_hue_lands_on_a_white_slot`). On the W0 parity wheel
`core.rgb_primary`'s first two stops resolve to red and green and `spec.cosmic_night`'s
first to blue, as the parity targets expect (`#00E5FF` now → blue, `#D500F9` → blue);
`tests/regression/test_mh_intent_parity.py` was not touched by the follow-up and its
results are unchanged.

**Conflict to decide (coordinator or owner).** The follow-up asked for both "rank
primarily by hue" and "amber → orange when orange exists". With the canonical amber
`#FFBF00` these disagree on a wheel that has both orange and yellow: amber's hue (84°)
is 26° from yellow (110°) and 31° from orange (53°), in OKLCh and in CIELCh alike
(83° / 103° / 60°), so hue-first sends it to **yellow**. It goes to orange on a wheel
with orange and no yellow (tested). Options: (a) accept it (physical amber, ~590 nm,
is between yellow and orange, nearer yellow); (b) move amber's canonical colour toward
SAE amber (`#FF7E00`, practically the `orange` preset); (c) rank by full ΔE_OK within
the slots that have a hue (amber → orange 0.145 vs yellow 0.158; purple → blue instead
of red on the four-colour wheel), at the cost of letting lightness override hue (a pale
sky blue `#87CEEB` would go to green, 0.301, instead of blue, 0.443). Implemented: (a), as directed.
Similarly, purple and magenta (328°) on a wheel with neither go to red (61° away) rather
than blue (64°): they sit almost midway.

## Guidance (config-hell avoidance)

`tag_guidance(profile, layout_hex=None, layout_model=None)` returns `None` when every
state that can carry a meaning does, else text with a paste-ready JSON snippet: each
channel that has an untagged state, with its **whole** `states` (so the snippet replaces
the object; tagged and open/closed states are kept as they are, with nulls left out),
each missing tag either a placeholder or a suggestion, and the suggestions listed after
it for the user to confirm. Placeholders (`<#RRGGBB or a colour name: …>`, `<one of: open,
circles, …>`, `<slow, medium or fast; delete this key if the state does not strobe>`)
are refused if pasted unfilled, so nothing unconfirmed can load silently.

Suggestions come from:

- **the state's name**, split into words: a colour state whose name is (or contains) a
  preset word (`red`, `dark-blue`, `Warm White`), or a colour wheel's `open` (white); a
  gobo state whose name contains a pattern word, singular or plural (`star` → `stars`,
  `stars_shake` → `stars`); a shutter state whose name contains `strobe` and a speed
  (`strobe_fast`). `cto`, `gobo4`, a bare `strobe` get a placeholder;
- **the fixture's xLights model** (`layout_color_tags`, below), which wins over the name.

`rig_tag_guidance(fixtures, models=())` runs it per profiled fixture, with that fixture's
own layout model when given, and returns one `RigTagGuidance(fixture_ids, text)` per
distinct guidance, naming every fixture it applies to (`"MH1, MH2 (profile
'synthetic_spot'): …"`); empty for a fully tagged rig.

**CLI seam.** `twinklr run` (and `inject`, `regenerate`, which share its path), right
after the rig checks (`preflight_render_policy`, then the `--layout` model check) and
before analysis, writes the guidance to `<output_dir>/<song_name>/profile_tags.txt` and
prints **one** yellow line: `NOTE: MH1, MH2: wheel or shutter states without a meaning
tag (hex, pattern, strobe) cannot carry the planner's colour, gobo or strobe choices;
paste-ready tags to confirm: <path>`. A fully tagged rig prints nothing and the file is
removed if an earlier run left one. It never fails the run. Follow-up revision: the
first pass printed the whole snippet inline per profile group on every run; the
coordinator asked for one concise line. A file was chosen over a flag because the
snippet is then at hand without a second run and nothing new is added to the CLI; this
mirrors how a run already leaves its other outputs in that directory. No new command.

Sample, `discrete_profile_payload` plus a `strobe_fast` shutter state and a `gobo4` gobo
state, as `tag_guidance` returns it:

```
8 wheel or shutter states do not say what they show, so the planner's colour, gobo and strobe choices cannot use them. Under the profile's `discrete`, replace each channel's `states` with the one below; fill every <...> placeholder (pasted unfilled, it is refused when the fixture file loads):
{
  "shutter": {"states": {
    "closed": {"range_min": 60, "range_max": 95, "value": 64, "settle_ms": 0},
    "open": {"range_min": 0, "range_max": 31, "value": 8, "settle_ms": 0},
    "strobe_fast": {"range_min": 100, "range_max": 149, "value": 120, "strobe": "fast"}
  }},
  "color": {"states": {
    "white": {"range_min": 0, "range_max": 9, "value": 0, "settle_ms": 120, "hex": "white"},
    "red": {"range_min": 10, "range_max": 19, "value": 14, "settle_ms": 120, "hex": "red"},
    "blue": {"range_min": 20, "range_max": 29, "value": 26, "settle_ms": 140, "hex": "blue"}
  }},
  "gobo": {"states": {
    "open": {"range_min": 0, "range_max": 7, "value": 0, "settle_ms": 150, "pattern": "open"},
    "dots": {"range_min": 8, "range_max": 15, "value": 10, "settle_ms": 150, "pattern": "dots"},
    "star": {"range_min": 16, "range_max": 23, "value": 20, "settle_ms": 160, "pattern": "stars"},
    "gobo4": {"range_min": 24, "range_max": 31, "value": 28, "pattern": "<one of: open, circles, triangles, stars, diamonds, clouds, prism, shatter, dots, flame, water, foliage, abstract>"}
  }}
}
These values are only suggestions; confirm each against the fixture before pasting:
  shutter.strobe_fast: strobe "fast" (suggested from the state name)
  color.white: hex "white" (suggested from the state name)
  color.red: hex "red" (suggested from the state name)
  color.blue: hex "blue" (suggested from the state name)
  gobo.open: pattern "open" (suggested from the state name)
  gobo.dots: pattern "dots" (suggested from the state name)
  gobo.star: pattern "stars" (suggested from the state name)
```

## Layout derivation (finding)

**xLights DMX models do carry colour-wheel slots; they carry nothing for gobo patterns or
strobe speeds.** Evidence, from the repository only (the owner's layout was not read):

- The repository's layout profiler already read `DmxColorWheelDMX<i>` and
  `DmxColorWheelColor<i>` (`i` < 20) from DMX models into `DmxColorWheelEntry(dmx_value,
  color)` (`profiling/layout/profiler.py`, `_extract_dmx_profile`, before this change),
  alongside `DmxColorType`. That reader had no test and no synthetic layout exercising
  it; the attribute names are therefore the repository's claim, not verified here
  against a file xLights wrote (that needs the owner's layout or an xLights run, both
  owner-gated). The only xLights-written DMX attributes the repository records as
  observed are `DmxChannelCount` (`rgb_effects.py`) and `DmxShutterOpen`
  (`evidence/2026-11-16-p2-xlights-result`). `DmxShutterOpen` is a single open
  threshold, which the profile's `open_state` already owns; no strobe-speed or gobo
  attribute appears anywhere in the repository.

So W1 derives colour tags only. `Model.dmx_color_wheel()` is now the one reader of those
attributes (the profiler uses it), and `layout_color_tags(profile, model)` proposes, for
each colour state, the colour of the slot(s) whose byte lies in the state's
`[range_min, range_max]`: a state with two different slot colours gets none, and a slot
whose byte is not an integer or whose colour is not `#RRGGBB` (or a preset name) is
skipped. Tested on a synthetic layout written by `p1_layout_xml` and parsed by the real
`load_layout`. The channel the slots belong to (xLights' colour-wheel channel attribute)
is not checked against the profile's colour offset: its attribute name is not in the
repository. Proposals are printed as suggestions, never applied. **Running this on the
owner's layout waits for the owner's word** (plan decision 4).

## Fingerprint and dump consequence

**No fingerprint changed.** The tag fields are excluded from dumps when absent
(`exclude_if`, the pattern this profile already uses for `dmx_min`/`dmx_max`), so an
untagged profile dumps byte-identically, and the render fingerprint and `twinklr show`
session id that hash it are unchanged: `tests/regression/test_mh_pins.py` passes
unchanged (fingerprints and frame hashes), and `test_an_untagged_profile_dumps_exactly_as_before`
pins the dump keys. A tagged profile does change both (a tag is rig data, as presets
are); under `twinklr run` it changes neither the planner's session nor its cache. The
ledger evidence (`test_state_tag_changes_identity_not_output`, six paths) renders
`masked_wheel_flick` on the four-head family rig, per-fixture and `base_config`, with
and without each tag: frames identical, fingerprint different.

`parity_rig` now carries tags; its frames are unchanged (the anchor still matches
`PINS["steady/mirror_wings/base"]`) and its fingerprint is not pinned anywhere.

## Ledger

`fixture.fixtures[FixtureInstance].config.physical_profile.discrete.states.{hex,pattern,strobe}`
and the same under `fixture.base_config.physical_profile`: `EFFECT_TEST`, evidence
`tests/unit/config/test_mh_state_tags.py::test_state_tag_changes_identity_not_output[<path>]`,
note "identity only; no consumer until song-intent W3 (rig offer) and W4 (colour and
gobo)". They are registered outside `test_physical_profile_field_changes_contract`'s
table because that table's registry payload has no gobo channel and its shutter has only
open and closed states, so a tag-only change could not be made there without changing
the base every other path is measured against. W3/W4 repoint them to the effect they add.

## What W3 and W4 will call

- **W3 (rig offer):** `tagged_colors(profile)` for the colours offered;
  `{p for p in GoboPattern if gobo_state(profile, p)}` for the gobos;
  `strobe_state(profile, speed)` per speed for the shutter actions (CLOSED/OPEN from
  `closed_state`/`open_state`). The offered wheel states join the entry-dip bound.
  `rig_tag_guidance` is the message to attach to a rig that offers nothing.
- **W4 (section colour and gobo):** palette role → stop → `nearest_color_state(profile,
  stop_hex[:7])` (palette stops may carry alpha; the lookup takes `#RRGGBB`); explicit
  preset → `nearest_color_state(profile, preset)` (through `COLOR_PRESET_HEX`); record
  `ColorMatch.fit` and `distance` when the fit is not `exact`. W3's offer can tell the
  planner which presets a wheel shows faithfully (`fit == "exact"`) and which only
  approximately. Gobo → `gobo_state(profile, pattern)`; `None`
  is repaired and fed back, never guessed.

## Verification

Run in this worktree on 2026-11-17, after the last edit of the follow-up:

| Command | Result |
|---|---|
| `uv run pytest tests -q --no-cov` | 6619 passed, 30 skipped, 24 xfailed (after the follow-up) |
| `uv run pytest tests/regression/test_mh_pins.py tests/regression/test_mh_intent_parity.py -q --no-cov` | 47 passed, 24 xfailed (45 pins unchanged; parity: anchor and guard pass, the 24 strict xfails still fail on their targets) |
| `uv run ruff check packages tests scripts` | All checks passed |
| `uv run ruff format --check packages tests scripts` | 1291 files already formatted |
| `uv run mypy packages/twinklr` | No issues in 645 source files |

TDD: the tag tests, the ledger evidence test and the CLI test were written and seen to
fail before the code they cover; the ledger guard
(`test_every_external_config_path_has_an_accountable_disposition`) reported the six tag
paths as unregistered before they were registered. The profiler slot test was added
after moving the reader and passes on the old reader too (it guards the move).

## Limits

- The owner's layout was not read; the colour-wheel attribute names are the
  repository's, not verified against an xLights-written file here.
- `COLOR_PRESET_HEX` values are chosen (restored from the deleted renderer), not
  measured.
- The `run` note prints on every run whose rig has untagged states, including the
  owner's until it is tagged.

## Review follow-up (2026-11-17, on `1f953f96`)

The independent review of `10f3ac49` asked for narrow changes (REQUEST CHANGES); the
integrator decided items 1–4, 6, 12 and the rig-level helpers. Every item was done. Not
committed; no `make validate`.

| # | Item | Done |
|---|---|---|
| 1 | `fit` was exact only at distance 0 | Graded: `exact` (ΔE_OK ≤ 0.02), `close` (ΔE ≤ 0.10 and hue ≤ 25°), `approximate` (hue ≤ 75°), `hue_mismatch`. `ColorMatch` is now `(state, hex, distance, hue_difference, fit, neutral_fallback)`; `hue_difference` is None when either colour is a white |
| 2 | No hue cap (blue → red on a white/red wheel) | Beyond 75°, or with no qualifying slot, the result is `hue_mismatch`: the nearest white slot (`neutral_fallback=True`), else the nearest hue. Pinned on white/red and open/CTO/CTB wheels |
| 3 | Purple `#800080` had magenta's hue | `#A020F0` (violet, 306°): purple → blue on white/red/blue/green, magenta on the eight-slot wheel |
| 4 | Amber `#FFBF00` (84°) → yellow | `#FFA000` (68°): amber → orange (close) where orange and yellow both exist |
| 5 | Guidance never clears for honestly untagged states | `"offer": false` (only `false`; refused beside a tag; left out of dumps when absent); `tag_guidance` treats it as settled. Ledger: two more paths, evidenced like the tags |
| 6 | `twinklr show` not wired | `show` calls the same helper (`cli/profile_tags.py`, `report_profile_tags`) with `wiring.layout_models` once its output directory exists, before any analysis |
| 7 | File write/delete could fail the run | Wrapped: a write failure prints the tags in full; a delete failure warns |
| 8 | Black → white | A request darker than Oklab L 0.15 gets no match (`None`): darkness is the dimmer's |
| 9 | Hard cut at chroma 0.04 | A pale tint (chroma < 0.10) takes the nearest white slot when it is nearer (Oklab) than the best slot with a hue, or when none qualifies. The catalog's pale stops (0.060–0.091) are `#B3E5FC`, `#FFCCBC`, `#80DEEA`, `#B39DDB`; every other non-white stop is 0.14 or more |
| 10 | Name suggestions too eager | A placeholder when the name has a modifier (`light`, `dark`, `deep`, `pale`), two colours, two patterns or two speeds (`strobe_slow_fast`) |
| 11 | Layout attribute names unverified | Said so in the user guide |
| 12 | `gobo_state` could pick the shaking copy | Shortest name, then first by name (`star` before `star_shake`); documented |
| 13 | Parity helper `nearest_state` calls the function under test | Noted here: the parity targets are mitigated by literal pins: `test_the_parity_palettes_resolve_as_the_parity_targets_expect` asserts red, green and blue for the three parity stops independently of the parity file |

**One addition beyond the decisions: `MIN_CHROMA_RATIO = 0.6`.** With the hue cap alone,
an open/CTO/CTB wheel answered red with CTO (`approximate`, 35° away), a white standing
in for a saturated colour by another name. A slot with a hue now qualifies only with at
least 0.6 of the request's chroma: red (0.258) needs 0.155 and a full CTO (`#FFB46B`) is
0.125, so red becomes a `hue_mismatch` on open; orange and amber (0.186, 0.172) still
take the CTO. 0.5 was tried first and let yellow and lime onto the CTO.

**Thresholds as tuned** (`state_tags.py`): `NEUTRAL_CHROMA` 0.04, `PALE_CHROMA` 0.10,
`MIN_LIGHTNESS` 0.15, `EXACT_DISTANCE` 0.02, `CLOSE_DISTANCE` 0.10, `CLOSE_HUE` 25°,
`HUE_CAP` 75°, `MIN_CHROMA_RATIO` 0.6. The cap at 75° keeps magenta → red (61°) on a
white/red/blue/green wheel and cyan → green (52°); 60° would send magenta to a white
fallback. Lightness counts in ΔE, so a darker or duller request than its slot grades
lower (e.g. `#00E676` → green is `approximate`, ΔE 0.11, 9°) although the dimmer could
supply the lightness; W4 may revisit that grading.

Every preset on five wheels (state, fit), pinned in
`test_every_colour_preset_resolves_by_hue_on_realistic_wheels`:

| Request | w/r/b/g | 8-slot | open/r/amber/pink/b/g | white/red | open/CTO/CTB |
|---|---|---|---|---|---|
| red | red exact | red exact | red exact | red exact | open mismatch |
| blue | blue exact | blue exact | blue exact | white mismatch | open mismatch |
| green | green exact | green exact | green exact | white mismatch | open mismatch |
| yellow | green approx | yellow exact | green approx | white mismatch | open mismatch |
| magenta | red approx | magenta exact | pink approx | red approx | open mismatch |
| cyan | green approx | cyan exact | green approx | white mismatch | open mismatch |
| orange | red approx | orange exact | amber close | red approx | cto approx |
| purple | blue approx | magenta approx | blue approx | white mismatch | open mismatch |
| amber | red approx | orange close | amber exact | red approx | cto close |
| lime | green approx | yellow close | green approx | white mismatch | open mismatch |
| white | white exact | white exact | open exact | white exact | open exact |
| warm_white, cool_white | white close | white close | open close | white close | open close |
| uv | blue approx | blue approx | blue approx | white mismatch | open mismatch |

Every catalog palette stop on the three colour wheels: no `hue_mismatch`, no saturated
stop on a white slot, whites on white (`test_no_saturated_palette_colour_lands_on_a_white_slot`).

**Parity.** `tests/regression/test_mh_intent_parity.py` was not edited in this round;
its targets go through `nearest_color_state(...).state` for `core.rgb_primary` (red,
green) and `spec.cosmic_night` (blue), which purple and amber do not touch: unchanged
(2 passed, 24 xfailed). `tests/regression/baselines/mh_intent_parity.json` was not
touched: its facts are the old renderer's. The old renderer's show projection
(`_closest_preset`) used the old preset table; that is a recorded fact, not something
this table follows. `COLOR_PRESET_HEX`/`canonical_hex` have no other consumer than the
profile's `hex` normalisation and these lookups; no committed rig tags `purple` or
`amber`, so no dump or fingerprint moved.

**Rig-level helpers for W3** (pure, tested on a mixed four-head rig):

- `rig_color_offer(profiles, color)` → `RigColorOffer(matches, status, worse)`: each
  fixture's `ColorMatch`; `all_exact_or_close`, `partial` (with `worse`, the fixtures
  less than close) or `unavailable` (every match None or `hue_mismatch`).
- `rig_gobo_offer(profiles, pattern)` and `rig_strobe_offer(profiles, speed)` →
  `RigStateOffer(states, available, missing)`, `available` being `all`, `some` or `none`.

Whether the heads of one section must share a resolved colour is left to W3/W4, as the
review listed it for W3.

**Guidance text** now also says how to opt a state out (`"offer": false`) and, when a
shutter has untagged states, that one variable slow-to-fast strobe range offers one
speed unless split into three states.

**CLI note.** One shared helper, `twinklr/cli/profile_tags.py`
(`PROFILE_TAGS_FILENAME`, `report_profile_tags`), used by `run`/`inject`/`regenerate`
and `show`. Tests: run (note once, file content), run on a tagged rig (no note, stale file
removed), show (note and file), and the write-failure fallback.

**Dumps and fingerprints.** Unchanged for untagged profiles: `offer` is excluded when
absent, like the tags. Pins: 45 passed.

### Verification (this round, after the last edit)

| Command | Result |
|---|---|
| `uv run pytest tests -q --no-cov` | 6718 passed, 30 skipped, 24 xfailed |
| `uv run pytest tests/regression/test_mh_pins.py -q --no-cov` | 45 passed |
| `uv run pytest tests/regression/test_mh_intent_parity.py -q --no-cov` | 2 passed, 24 xfailed |
| `uv run ruff check packages tests scripts` | All checks passed |
| `uv run ruff format --check packages tests scripts` | All files formatted |
| `uv run mypy packages/twinklr` | No issues in 645 source files |
