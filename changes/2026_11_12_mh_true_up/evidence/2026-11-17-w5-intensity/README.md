---
type: evidence
status: complete
area: engineering
change: 2026_11_12_mh_true_up
created: 2026-11-17
updated: 2026-11-17
---

# W5 — intensity on the dimmer, and the show's focal role (W9, focal half)

**Provenance.** Implemented by an executor agent on 2026-11-17 in the worktree
`twinklr-mh-true-up`, branch `feat/mh-true-up-p3`, from `cbf4a684`. Uncommitted; the
integrator commits. Plan of record: [song-intent rendering](../../plan/song-intent-rendering.md),
task W5 and the focal-role half of W9, under the owner's ruling that song intent is
rendered, never cut. No provider call, no network, no xLights, nothing under `~/xlights`,
`data/` or `artifacts/`; every rig, song and template here is synthetic or the
repository's catalog. `make validate` was not run (reserved for the integrator); the
commands it wraps were run one by one (§ Verification).

**The owner has not seen it**: the W5 view is pending (§ What to look for). Every value in
the table below is a first proposal for that view.

## What was built

| Area | Change |
|---|---|
| `sequencer/moving_heads/intensity.py` (new) | The one place for intensity: the table (`SHAPES`, `ACCENT`, `dramatic_period_beats`), the curve (`accent`), the focal mapping (`effective_intensity`), the shaping of a section's compiled cues (`shape_section`), the trace line (`describe_intensity`) |
| `sequencer/moving_heads/pipeline.py` | Per section, the effective intensity (asked, adjusted by the focal role); a shaped level is applied to the compiled cues inside `compile_section`, before the dark spans and every boundary dip; trace `section_looks[].intensity`; `RenderingPipeline(focal_roles=...)`, `rendered_focal_roles()`, trace/checkpoint `focal_roles`; intensity removed from the "not rendered yet" diagnostic; a warning per section where a head has no dimmer axis |
| `identity.py` | `RENDERER_REVISION` 4 → 5; the fingerprint hashes `focal_roles` (only the roles that change a section's intensity, only when there are any) |
| `song_intent.py` | `RENDERED_INTENT_FIELDS` gains `intensity`; `describe_look` adds the intensity line |
| `show_coordination.py` | `moving_head_focal_roles`: the heads' role per macro section (none for a section that names none, or contradicting roles across moving-head targets) |
| `pipeline/show_stages.py` | `show` passes the focal roles to the render; the "focal role not projected" diagnostic is removed |
| Planner (`context.py`, `stage.py`, `orchestrator.py`, `definitions/moving_heads.py`, `definitions/show.py`, prompts) | `MovingHeadPlanningContext.head_focal_roles` (show only, from `moving_head_focal_roles`), in the prompt and the cache key; the user prompt lists each section's role and the rule; the developer prompt says what each intensity plays; the offer line says where intensity cannot pulse |
| `rig_repair.py` | A DRAMATIC/INTENSE section on a rig where some or no head has a dimmer axis is recorded as not shaped (kept; fed back) |
| Reporting (`collect.py`, `rerender.py`, `generator.py`) | `RecordedRender.focal_roles`, re-rendered with; a `focal roles` mismatch is named; the report's `played` line for intensity (via `describe_look`); `not_rendered` no longer lists intensity |
| Coordinator additions (beyond-grid, same files) | `beyond_grid` in planner and judge variables and one line in each prompt; the macro table, palette lines, focal arc and focal roles leave out sections beyond the grid; `unanswered_high_cues(unplannable=...)` skips their lyric cues (§ Coordinator additions) |
| Tests | `test_intensity_render.py` (new), parity xfails removed, `INTENSITY_PINS`, prompt/cache/repair/selector/show-coordination/integration tests (§ Tests) |
| Docs | User guide § "How a section's intensity reaches the lights" and the passages that listed intensity or the focal role as not rendered; pipeline guide, developer guide, overview, README, glossary, multi-agent planning, product overview, QA runbook, `context/current-state.md`, the plan's W0 table |

## The table (proposed, for the owner's view)

All in `packages/twinklr/core/sequencer/moving_heads/intensity.py`.

| Level | Plays | Accent every | Floor gain (headroom) | Peak gain (headroom) | Dip floor (at full) |
|---|---|---|---|---|---|
| `as_authored` (null), `SLOW`, `SMOOTH`, `FAST` | the template as authored, byte for byte | — | — | — | — |
| `DRAMATIC` | a pulse on the strong beats | half bar in an even meter of ≥ 4 beats (2 beats in 4/4, 3 in 6/8 counted in eighths), else the bar (3 in 3/4, 2 in 2/4, 5 in 5/4) | × 1.10 | × 1.50 at the accent | 75% of full |
| `INTENSE` | a harder pulse on every beat | 1 beat | × 1.15 | × 1.75 at the accent | 60% of full |

**The curve.** The accent `e` is 1 on the first frame at or after an accent beat and eases
to 0 over one beat (`ACCENT.decay_beats`, or the period if shorter) as `(1 − p)²`, `p` the
share of that beat elapsed in musical time; then 0 until the next accent. A quadratic
ease-out: the level is at its accent on the beat's first frame and falls fastest right
after, so it reads as a hit, not a fade. Beats count from the section's first downbeat
(the part's, for a part), so DRAMATIC's accents land on beats 1 and 3 in 4/4.

**Per frame**, with `a` the authored level and `top` the dimmer axis' operable maximum:

- `a` = 0, or the cue's shutter extinguishing there: untouched (the dark frames are the
  template's).
- `a` below `top` (headroom): `min(top, a × (1 + floor_gain + peak_gain × e))`. The floor
  rises everywhere, the accent rides on top, scaled by the template's own level, so a
  template's own pulse still reads under it.
- `a` at `top` (every catalog family): `top × (1 − dip_depth × (1 − e))`, a
  **dip-and-return**: full on the accent, easing down to `top × (1 − dip_depth)` before
  the next, back to full on it. The only case where a frame plays below the template, and
  only where there is no headroom. Never zero.

Why these values: INTENSE must read harder than DRAMATIC on both kinds of template (higher
floor and peak, deeper dip, every beat). The headroom floor gain stays below 0.25 so a
template alternating 0.8 and 0.3 still falls back from full inside its 0.8 beat (its own
shape stays readable and the parity row's "a peak after every beat" holds). The dip floor
keeps a full-level family clearly lit (60% / 75%), never a strobe. One beat of decay
keeps the shape a pulse at 78 BPM (769 ms) as at 120. None of this is measured or
accepted; the owner judges it.

### Each shape in numbers (MH1, dimmer bytes, steady grids, beat 15 ms off the frame grid)

Scratch: `w5/tempo_examples.py`. "Accent" is the first frame at or after the beat; then
+100 ms, half a beat later, and the last frame before the next beat.

| Template (authored) | Level | 120 BPM (beat 500 ms) | 78 BPM (beat 769 ms) |
|---|---|---|---|
| `mirror_wings` (full, 255) | INTENSE: dip-and-return every beat | 255, 218, 181, 153 on every beat; min 153 | 255, 230, 179, 153 on every beat; min 153 |
| `mirror_wings` (255) | DRAMATIC: every 2 beats | beat 1: 255, 232, 208, 191; beat 2 held at 191; beat 3 as beat 1 | beat 1: 255, 240, 208, 191; beat 2 at 191 |
| held half level (128) | INTENSE: headroom pulse | 223, 196, 167, 147 every beat (authored 128) | 223, 205, 166, 147 |
| held half level (128) | DRAMATIC | beat 1: 191, 173, 154, 140; beat 2 at 140 | beat 1: 191, 179, 153, 140; beat 2 at 140 |
| own pulse 0.8/0.3 (204/77) | INTENSE: accent on the authored pulse | 0.8 beats: 255, 255, 255, 235; 0.3 beats: 134, 117, 100, 88 | 0.8 beats: 255, 255, 255, 235; 0.3 beats: 255*, 123, 100, 88 |

\* At 78 BPM the template's own 0.8→0.3 change lands one frame after the accent frame
(the step's phase origin is its quantized start), so that frame is still the 0.8 level
under the accent: the template's timing, not the shaping.

In words: on a full family INTENSE punches full on every beat and sags to 60% before the
next; DRAMATIC punches full on beats 1 and 3, sags to 75% over the beat and holds there
through beats 2 and 4. On a template below full the light gets brighter overall and
peaks on the beat.

## The focal role in `twinklr show` (W9, focal half)

| Heads' macro focal role | Effective intensity |
|---|---|
| LEAD | one step toward INTENSE: as authored, SLOW, SMOOTH, FAST → DRAMATIC; DRAMATIC → INTENSE; INTENSE stays |
| SUPPORT | the planner's choice |
| REST | capped at the identity: DRAMATIC, INTENSE → as authored; the others stay |
| none for the moving-head targets, or contradicting roles across them | the planner's choice |

`twinklr run` has no focal role and is unchanged. The planner's prompt under `show` lists
each section's role and states the rule (the planner still sets intensity from the
energy; the role is applied on top). A role that changes a section's intensity is render
identity (`rendered_focal_roles`): the fingerprint hashes it, the trace and the plan
checkpoint record it as `focal_roles`, `eval-report` re-renders with it and names
`focal roles` when they differ (integration-tested). A SUPPORT role, or REST on an
identity level, changes no byte and is not recorded, so a show whose heads support renders
and identifies them exactly as `twinklr run` does (the existing integration test).

**Consequence for the owner:** on the catalog families LEAD means DRAMATIC's
dip-and-return — more motion in the light, not more light. "Hotter" in the parity row is
met on the half-level test template; on a full family it cannot be brighter.

## Composition with W4

- Shaping runs inside the section compile, after the held colour/gobo and overlays, and
  before `_dark_over_spans`; boundary dips, deferrals and kept colours are computed on the
  shaped cues, and their darkness is written over the shaped dimmer. A dark span stays
  dark; a colour dip stays dark (tests: `test_a_dark_span_stays_dark_under_intensity`,
  `test_a_colour_dip_at_a_lit_boundary_stays_dark_under_intensity`: same dark frames, same
  wheels, same everything but the dimmer).
- Only the dimmer of lit frames changes, so wheel turns, the gate's dark phases, entry
  windows and transactions are as before; the gate compiles unshaped (it never sees an
  intensity) and that is equivalent.
- W4's tests and pins pass untouched (`INTENT_PIN`, `FAST_INTENT_PIN` frames and `.xsq`
  unchanged; their plans set no intensity).

## Physical limits

- **No dimmer axis** (shutter-only darkness): that head plays as authored; the trace's
  shape lists it under `unavailable`, a warning names it per section, the offer's `hit`
  is `some`/`none` and the prompt says intensity cannot pulse there; `repair_rig_intent`
  records a DRAMATIC/INTENSE choice as not shaped (kept, fed back so the planner can use
  events or colour).
- **Dimmer `travel_speed_per_s`**: where the shape's steepest frame-to-frame step (beyond
  the template's own change) exceeds `speed × 20 ms`, accent and dip are scaled by
  `allowed / steepest` (same timing, smaller amplitude: the nearest renderable shape);
  recorded per head under `degraded`. Test: at 4/s every lit step is ≤ 0.08 (+1 word).
- **Dimmer `latency_ms`**: the accent is commanded that much earlier, so the light lands on
  the beat; recorded under `lead_ms`. Test: 40 ms latency → the accent frame is the first
  at or after `beat − 40 ms`. No catalog or test profile declares either today; the
  owner's rig does not (as far as the repository shows), so both paths are dormant there.

## Trace, report, diagnostics

`section_looks[]` gains `intensity` for every section that sets an intensity, or whose
focal role changes it: `asked`, `focal_role` (when given and it changed something),
`effective`, and `shape` (null for an identity level) with `period_beats`, `decay_beats`,
`floor_gain`, `peak_gain`, `dip_floor`, `applied` (`headroom_pulse`,
`authored_pulse_accent`, `dip_and_return` → heads), and when present `degraded`,
`lead_ms`, `unavailable`. `eval-report` shows it as a `played` line, e.g. "intensity
DRAMATIC: a pulse on the beat every 2 beats: full on the accent, down to 75% between on
MH1, MH2, MH3, MH4". The "not rendered yet" diagnostic, `not_rendered` and the vision
judge's `not_rendered_yet` no longer list intensity; the `show` diagnostic about the focal
role is gone.

## Revision, fingerprints, caches

- **`RENDERER_REVISION` 4 → 5**: a plan that sets DRAMATIC or INTENSE, or a show whose
  heads LEAD (or REST over a shaped level), renders differently for an unchanged plan and
  rig. Every render fingerprint changes.
- **Pins:** all 42 family pins, `MULTI_PIN`, `GATED_PIN`, `INTENT_PIN` and
  `FAST_INTENT_PIN` re-recorded fingerprint only; every frame and `.xsq` hash unchanged
  (the script checks frames/`.xsq` before rewriting: `w5/rerecord_pins.py`). `INTENT_PIN`
  and `FAST_INTENT_PIN` did not change in frames because their plans set no intensity.
  Combined-show golden moving-head fingerprint `5fd51634…` → `94b523ea…`; its effects and
  trace hashes unchanged.
- **New pins** `INTENSITY_PINS` (steady grid, one 8-bar section, family rig):
  `full/mirror_wings/INTENSE` (dip-and-return), `headroom/intensity_half_hold/DRAMATIC`
  (held 0.5), `authored_pulse/intensity_authored_pulse/INTENSE` (own 0.3/0.8 pulse).
- **Planner cache:** re-keyed for every song by the prompt-pack change (developer and user
  prompts), and under `show` by `head_focal_roles`; every song plans again once (paid).
- **Checkpoints:** a show checkpoint now carries `focal_roles` when a role changed a
  section; older checkpoints re-render with none and their fingerprint differs anyway
  (revision 5).

## Parity rows turned green

`tests/regression/test_mh_intent_parity.py`, xfail markers removed, no assertion changed:
`intensity_dramatic`, `intensity_intense`, `intensity_dramatic_on_authored_pulse`,
`intensity_intense_on_authored_pulse` (W5) and `show_focal_lead` (W9). None of the four
W5 rows uses a full-level template, so the dip-and-return never meets "never below the
authored level" there; nothing had to be bent. Suite: 13 passed, 13 xfailed (was 8 / 18);
`--runxfail`: the 13 remaining (W6 6, W7 3, W8 4) fail on their own target assertions.

## Byte matrix (unchanged cases)

Harness: `w5/matrix_w5.py` (the W3/W4 matrix with plan C rendered at six intensities:
as authored, SMOOTH, SLOW, FAST, DRAMATIC, INTENSE; the record normalised also for
`focal_roles`), run on `git archive cbf4a684` and on this tree: 405 configurations
(9 rigs × 3 fixture timings × 5 grids, 3/4 included × 3 policies) × 8 renders; 39,285 leaf
comparisons (`w5/compare_w5.py`). No render errored on either tree.

- **Identical in all 405 configurations:** the gate (admitted, exclusions, entry dips);
  plans A and B (as authored): frames, segments, normalised record and trace, `.xsq`,
  `.xtiming`, `.xmap`; plan C at as authored, SMOOTH, SLOW and FAST: frames, segments,
  `.xsq`, `.xtiming`, `.xmap` — against the same plan on the base tree **and** against
  the base tree's DRAMATIC plan C (which base renders as authored). The identity levels
  move no byte.
- **Different by design only:** every fingerprint and raw trace (revision 5); plan C's
  normalised record and trace at every level, because the "not rendered yet" diagnostic
  no longer names intensity, so the tail section (SLOW, nothing else unrendered) has none
  (checked on one configuration by diffing the records: that diagnostic is the only
  difference) and `section_looks` gains the intensity entry; plan C at DRAMATIC and
  INTENSE: frames, segments and `.xsq`. Against the as-authored plan C on this tree, the
  DRAMATIC and INTENSE frames differ **only on the dimmer channel**, and not one frame
  changes between a zero and a non-zero dimmer, in all 405 configurations (`vs_authored`:
  channels `["dimmer"]`, zero-dimmer frames moved 0).

## Coordinator additions (beyond the beat grid)

Folded into this round on the coordinator's request, alongside another agent's
`song_structure()` (kept as it was):

1. `build_planner_variables` and `build_judge_variables` pass `beyond_grid`; the planner's
   user prompt says, after the Song Structure table, "The last N s of the song lie beyond
   the detected beat grid and are not planned (ids left out)."; the judge's adds "a plan
   without them is complete".
2. `for_prompt` leaves sections beyond the grid out of the macro table, the per-section
   palette lines, the focal arc and the heads' focal roles (the rig offer's palette roles
   already used the plannable sections).
3. `unanswered_high_cues(..., unplannable=...)` skips lyric cues in sections beyond the
   grid; the orchestrator passes `song_structure()["beyond_grid"]["section_ids"]`. Cue
   binding iterates only the plan's sections, so it needed no change.

Tests: `TestThePlannerIsNotShownASectionBeyondTheGrid` in `test_context_grid.py` (planner
prompt line and omissions, judge prompt line, advisory skip).

## Tests

- New `tests/unit/sequencer/moving_heads/test_intensity_render.py` (40): the DRAMATIC
  period by meter; the focal mapping table; identity levels byte-identical on a full
  family, an envelope family and a half-level template; INTENSE on a full family at 120
  and 78 BPM (full on every lit-across beat's first frame, below full either side, never
  under 60%, dark frames and every other channel unchanged); DRAMATIC shallower, its
  accents every 2 beats in 4/4 and every 3 in 3/4; headroom rises and never drops; dark
  span and colour dip composition; slow dimmer degraded; dimmer latency lead; no dimmer
  axis; the trace record; LEAD = DRAMATIC, REST over INTENSE = as authored, SUPPORT
  neither identity nor recorded.
- `INTENSITY_PINS` (3); parity rows (5 un-xfailed).
- Prompt tests (intensity line on a dimmerless rig; the show's focal-role block), cache
  key (`head_focal_roles`), rig repair (intensity recorded as not shaped), selector
  (its DRAMATIC/INTENSE now change the dimmer only; FAST does not), show coordination
  (`moving_head_focal_roles`), integration (`show` with LEAD heads: trace, checkpoint,
  `eval-report` match, lost roles named).
- Changed for intended behaviour: two rendering-pipeline tests that asserted intensity was
  reported unrendered; the report test (intensity is played, not unrendered); the
  combined-show integration test that asserted the focal-role diagnostic; the rerender
  contract test (`RecordedRender.focal_roles`); the golden fingerprint.

## What the owner should look for (W5 view; PENDING-OWNER)

All open owner questions are collected in one list:
[owner decisions pending](../../plan/owner-decisions-pending.md).

Render a song with sections set to DRAMATIC and INTENSE over catalog families (full
level), and, under `twinklr show`, sections where the heads LEAD and REST:

1. INTENSE on a full family: full on every beat, sagging to 60% before the next. Is the
   dip deep enough to read, or too much (a flicker)? Proposal: `dip_depth` 0.40.
2. DRAMATIC: full on beats 1 and 3 (4/4), sagging to 75% and holding through 2 and 4. Is
   the half bar the right period, and 75% the right floor? (The deleted renderer pulsed
   DRAMATIC every 5 beats, 131–255; not carried over.)
3. The decay: one beat, quadratic. Does it read as a hit on the beat at both tempos?
4. LEAD under `show` plays DRAMATIC on an as-authored section: on a full family that is a
   moving, not a brighter, light. Acceptable as "hotter", or should LEAD on a full family
   mean something else?
5. SLOW and FAST play as authored (the owner's 2026-11-12 ruling; the planner is told).
   The deleted renderer's SMOOTH calmed an energetic template (W0 record); here SMOOTH is
   the identity.

Proposals (all in `intensity.py`): `SHAPES` (floor and peak gains, dip depths),
`ACCENT.decay_beats`, `dramatic_period_beats`, the quadratic curve, the LEAD/REST mapping.

## Cut or deferred

Nothing in the brief was cut. Not done because out of W5's scope: intensity does not
reach motion (the plan routes motion through presets); the deleted renderer's 5-beat
DRAMATIC period and sample-index pulse are not carried over (as the W0 record says).
`hit` (HIT events) is still not rendered (W6).

## Verification (this tree, fresh)

Run after the last code edit, 2026-11-17:

| Command | Result |
|---|---|
| `uv run pytest tests -q --no-cov` | 6929 passed, 30 skipped, 13 xfailed (was 6860 / 30 / 18 at `cbf4a684`; the count includes the coordinator additions and the other agent's beyond-grid tests in this tree) |
| `uv run pytest tests/regression/test_mh_pins.py -q --no-cov` | 50 passed (46 re-recorded fingerprints with frames/`.xsq` unchanged, the intent pins, 3 new intensity pins) |
| `uv run pytest tests/regression/test_mh_intent_parity.py -q --no-cov` | 13 passed, 13 xfailed; `--runxfail`: 13 failed, every one an `AssertionError` on its target (W6 6, W7 3, W8 4), 13 passed |
| `uv run ruff check .` | All checks passed |
| `uv run ruff format --check .` | 1303 files already formatted |
| `uv run mypy .` | No issues in 652 source files |
| Byte matrix (`w5/run_matrix.sh`, base `cbf4a684`) | As § Byte matrix |

Scratch (session-local, not committed):
`/private/tmp/claude-501/-Users-ondeck-work-github-twinklr/9cfb5b66-fff4-47db-adcb-766b50dc61e9/scratchpad/w5/`
(`matrix_w5.py`, `compare_w5.py`, `run_matrix.sh`, `rerecord_pins.py`,
`intensity_pins.py`, `tempo_examples.py`).

## Review fix round (2026-11-17, on `f0e2cff6`)

The independent review of `9d607f45` confirmed byte identity, pins, parity and the
dark-frame guarantees and returned REQUEST CHANGES (H1, H2, M1–M4, L1–L6). Done here: H1,
M1, M2, M3, M4, L1–L6; H2 is the owner's decision and only a comparison variant was
prepared (below). Uncommitted, no `make validate`, no provider call. Where this section
and the text above differ, this section is current. The reviewer's scripts
(`w5rev/tools/`) were run before and after; outputs in `w5/fix_before/` and
`w5/fix_after/`.

### What changed

| # | Item | Done |
|---|---|---|
| H1, L1 | A lit window with no accent beat played flat (cascades under DRAMATIC: MH2/MH3 of `fly_in_cascade`, MH1/MH4 of `fly_out_cascade` at 191 throughout); a head revealed mid-beat came in partway down the decay | The shaping moved out of the section compile to one pass over each section's cues **once every darkness is placed** (dark spans, boundary dips, deferred turns, entry windows), and works per **lit run** (consecutive lit frames of one head). Every run starts on an accent (at the run's level, decaying from there) and rejoins the beat accents. Frame tests: both cascades × both levels (every window starts full, eases off, never under the floor), reveal after a dark span ending mid-beat, reveal after a colour dip at 170 BPM |
| M1 | "Full" was decided per frame (a ramp reaching full dropped 64 words; a 1.0/0.6 pulse inverted; 0.87–<1.0 played flat at full) | Decided per lit run by its highest authored level `M` against `HEADROOM_BELOW = 0.85` of the dimmer's top. Both cases are now a **gain on the authored level**: full runs `a × (full_peak − (full_peak − full_floor)(1 − e))` (ramps and the template's own pulse keep their form); headroom runs `a × (1 + g(floor + peak·e))` with `g` capping the gains so the run's peak reaches the top at most (no clipping plateau). Frame tests: ramp to full (never above authored, never below the floor of it, no drop where it reaches full), 1.0/0.6 pulse not inverted, 0.9 held level pulses |
| M2 | Prompts and docs did not say that at full level the pulse dips below the authored light | Developer prompt: at full level DRAMATIC/INTENSE "add movement, not brightness … eases below it between accents (about 75% / 60%)", below full they raise the light; the user prompt's colour line no longer says "brightness is `intensity`'s"; the user guide states the mean levels. LEAD wording and the table left as they were (H2) |
| M3 | Missing frame tests | Added (see H1, M1, M4, L2), plus LEAD vs SUPPORT on a catalog family, pinned as today's behaviour (mean 0.75–0.85 of SUPPORT) until the owner rules on H2 |
| M4 | The accent was quantised one frame after the template's own beat edge (a 20 ms frame at the floor before the snap to full, 8 cases at 170 BPM) | Accents start on the frame **nearest** the beat (`quantize_cue`, as the compiler places step starts and so the template's beat edges); a run starting at most one frame before an accent takes that accent at its first frame. The reviewer's 170 BPM colour-dip check (`w4low.py`) now reports no reveal below full |
| L2 | Latency lead unbounded; the first downbeat after an unshaped section lost | Lead = `min(latency_ms, half the section's shortest beat − 1 ms)`; no accent before the section's first frame. Test: 300 ms latency at 120 BPM leads by 249 ms and the section's first frame is full. The template's own dimmer edges are not led (documented) |
| L3 | Partial focal naming applied LEAD to the whole rig | Decided: the heads render as one rig, so a role applies only where **every** moving-head target holds it; none named → planner's choice silently; different roles, or a role for some targets and none for others → planner's choice with a warning naming each target's role. Same function feeds the planner's prompt, so it is told only the roles that apply. Tests |
| L4 | `beyond_grid.seconds` measured from the extrapolated end of the last bar; warning repeated on every call | Measured from where the render goes dark: the beat grid's covered span end (last beat + one interval, or the song's edge) on the frame grid, as the renderer's cue limits put it; the warning is logged once per planning context (a private flag). Tests: quarter-beat grid → `from_ms` 182740 (not 185000), 14.7 s; three calls and a prompt build log once |
| L5 | A lyric cue in the clamped tail of a straddling section bound silently to the last grid beat | Chosen: **recorded**, not skipped. The section is planned and the accent still plays at the end of the lit song, which serves the lyric better than dropping it, and the planner should know it is not on the lyric: `ADJUSTED` "lyric moment cue 'x' at T ms lies beyond the detected beat grid, where the render is dark from D ms: placed on the grid's last beat in the section (bar b beat k)". Advisories (`unanswered_high_cues`) are unaffected (the cue has an event). Test |
| L6 | `_shape_head` long; `_AccentTiming` with special branches | Replaced by `_Grid` (the section's accent frames, lead clamped, computed once per head), `_lit_runs`, `_gains` (per run: the shape name and per-frame `(fixed, moving)` gain, `moving` scaled for a slow dimmer) and a short `_shape_head`; the `_Frame`, `_shaped` and `_AccentTiming` helpers are gone |

Also fixed on the way: under a slow dimmer the scale now shrinks the dip toward the
authored level (the first rewrite shrank the accent above the floor instead; caught by
the reviewer's `limits.py`: `[153, 173, …]` → `[235, 255, 253, …]` at 4/s, as before).

### Numbers (MH1 unless named; 120 BPM, beats 15 ms off the frame grid; `w5/fix_numbers.py`)

| Case | Before (HEAD `f0e2cff6`) | After |
|---|---|---|
| `fly_in_cascade` DRAMATIC, MH2, lit 1520–2000 ms (beat 3, not accented), every 40 ms from 1500 | 0, 191 × 12 (flat) | 0, 250, 241, 232, 224, 217, 211, 206, 201, 198, 195, 193, 192 |
| Ramp to full (envelope, attack 1 beat) DRAMATIC, 2000–3000 ms every 40 ms (authored 0, 10, 31, 51, 71, 92, 112, 133, 153, 173, 194, 214, 235) | 0, 15, 43, 69, 93, 116, 137, 158, 178, 198, 218, 238, 255, then 191 at the frame it reaches full | 0, 10, 29, 47, 64, 79, 94, 108, 122, 136, 149, 163, 177 (the ramp scaled by the decaying gain; full on the next accent) |
| Same, INTENSE | 0, 17, 49, 78, …, 250, 255 | 0, 10, 29, 45, 59, 72, 83, 94, 104, 113, 122, 132, 142 |
| Dark span 2000–2260 ms then INTENSE, from 2240 every 40 ms | 0, 177, 169, 163, 159, 156, 154, 255 (beat), … | 0, 247, 232, 218, 206, 195, 185, 255 (beat), … (2260 itself: 255) |
| Held 0.9 INTENSE, 2000–3000 ms every 40 ms | 255 × 13 (flat: clipped at full) | 138, 222, 209, 196, 185, 175, 166, 159, 152, 147, 143, 140, 138 |
| 170 BPM, colour dip before section 2 (starts 5662.1 ms), every 20 ms from 5460 | 190, 183, 177, dark × 7, **153**, 255, 244, … | 183, 177, 172, dark × 7, **255**, 244, 233, … |
| The reviewer's `shape.py` (6 families × 5 grids incl. 3/4 and a drifting tempo × 2 levels), with its accent frames quantised to the nearest frame as the renderer now does | 0 problems (with its ceil quantisation) | 0 problems |

### Revision, pins, matrix

- **`RENDERER_REVISION` 6 → 7**: bytes change for an unchanged plan that sets DRAMATIC or
  INTENSE (or a show whose focal role makes one).
- **Pins:** every fingerprint re-recorded; every frame and `.xsq` hash unchanged except two
  intensity pins: `headroom/intensity_half_hold/DRAMATIC` (its first lit run, after the
  section's entry window on beat 2, now starts on an accent: L1) and
  `authored_pulse/intensity_authored_pulse/INTENSE` (gains capped so the 0.8 beats peak at
  full instead of clipping: M1). `full/mirror_wings/INTENSE` frames unchanged. Golden
  moving-head fingerprint → `de596d6a…`, effects and trace unchanged.
- **Byte matrix** against `f0e2cff6` (405 configurations × 8 renders, 39,285 leaves):
  identical in all 405 — the gate; plans A and B (frames, segments, normalised record and
  trace, `.xsq`, `.xtiming`, `.xmap`); plan C as authored, SMOOTH, SLOW, FAST (the same, the
  normalised record and trace included). Different by design: plan C at DRAMATIC in all 405
  (frames, segments, `.xsq`, trace: run-start accents on the cascades and the parts) and at
  INTENSE in 189 (216 identical: where every lit run already started on a beat); in all of
  them only the dimmer channel differs from the as-authored plan C on this tree and not one
  frame moves between zero and non-zero dimmer. No render errored.
- **Parity:** 13 passed, 13 xfailed; `--runxfail` 13 failed, every one an `AssertionError`
  on its target. No assertion changed.

### H2: the headroom comparison variant (not in the product)

`w5/headroom_variant.patch` (one file, `intensity.py`, +17/−10): the `SHAPES` table gains
entries for the identity levels and REST, and `effective_intensity`'s REST line returns
`"REST"` — table values plus that one line, as the module is now structured
(`shape_for(level)` looks every effective level up in `SHAPES`; the product has no entry
for the identity levels, so they stay byte-identical).

| Level (variant) | Gain on a full family | Mean lit level, `mirror_wings` | `fly_in_cascade` |
|---|---|---|---|
| as authored, SLOW, SMOOTH, FAST | 0.82 steady | 0.820 | 0.820 |
| REST (focal) | 0.70 steady | 0.698 | 0.698 |
| DRAMATIC | 0.90, accents to full every half bar | 0.919 | 0.935 |
| INTENSE | 0.90, accents to full every beat | 0.935 | 0.935 |
| LEAD on an as-authored section (→ DRAMATIC) | as DRAMATIC | 0.919 | 0.935 |
| Product today, for comparison: DRAMATIC / INTENSE / identity | | 0.795 / 0.741 / 1.000 | 0.838 / 0.741 / 1.000 |

Verified: `git apply --check` on this tree; applied to a scratch copy, its frame check
(`w5/variant/check_variant.py`) passes: no zero on a lit frame, the dark frames equal the
product's as-authored render, REST < verse < DRAMATIC ≤ INTENSE and LEAD above the verse in
mean lit level (on the cascade DRAMATIC and INTENSE are equal: every lit window is one beat
and starts on an accent). The variant changes identity-level bytes, so it needs the owner's
ruling; the integrator applies it to a scratch copy for a comparison render.

### Verification (after the last code edit)

| Command | Result |
|---|---|
| `uv run pytest tests -q --no-cov` | 6955 passed, 30 skipped, 13 xfailed |
| `uv run pytest tests/regression/test_mh_pins.py -q --no-cov` | 50 passed |
| `uv run pytest tests/regression/test_mh_intent_parity.py -q --no-cov` | 13 passed, 13 xfailed; `--runxfail`: 13 failed (13 `AssertionError`s on their targets), 13 passed; the test file unchanged from HEAD |
| `uv run ruff check .` | All checks passed |
| `uv run ruff format --check .` | 1303 files already formatted |
| `uv run mypy .` | No issues in 652 source files |
| Byte matrix (`w5/run_matrix.sh`, base `f0e2cff6`; `w5/compare_w5.py matrix_head.jsonl matrix_fix.jsonl`) | As above |
| Variant (`w5/headroom_variant.patch`) | `git apply --check` clean; `w5/variant/check_variant.py` on a patched scratch copy: PASS |
