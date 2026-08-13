# P1P-T5 — Scheduler + preset + calibration truth

Phase: 1P (Render Truth) · Lane: R (render repair, serial) · Executor: opus · Verifier: opus · Depends on: P1P-T3

## Objective

Stop the renderer from silently emitting nothing, emitting the wrong thing, or emitting
the opposite of the intent. Short sections render; narrative templates play their whole
arc; the one template that overruns its section by 2× is clipped; blackouts are black;
dimmers respect the anti-flicker floor every template declares; and the fixture
calibration the user configured actually limits the emitted DMX.

## Evidence & background

Findings: **CF-6** = **P4-F4 / F5 / F6 / F8 / F9 / M1 / M2**. Two of these (M1, M2) were
added by the phase verifier and are output-changing.

Line numbers are hints from baseline `aa8d325`. Re-verify before editing.

### 1. Short sections render nothing (P4-F4). Verbatim:

> `compile/scheduler.py:96-107`: when `duration_bars // cycle_bars == 0`, `schedule_repeats`
> logs a warning and returns `ScheduleResult(instances=[])`. `compile_template` then produces
> zero segments (`template_compiler.py:119` iterates an empty list) and the section is dark.
> No exception, no validation failure — only a `logger.warning` that the CLI does not
> surface at default verbosity.
>
> **[V] Corrected census:** **34** templates have `cycle_bars = 4.0`, **1** has 8.0
> (`ambient_random_wash`), **2** have 2.0 (`ballyhoo_chaos`, `build_drop_recover`) —
> AST-verified; the original report said 35/1/2. Restating the consequence precisely:
>
> - a **1-bar** section renders nothing for **all 37** templates (the smallest cycle is 2.0);
> - a **1–3-bar** section renders nothing for **35 of 37** (the 34 at `cycle_bars=4.0` plus
>   the one at 8.0);
> - a **1–7-bar** section renders nothing for `ambient_random_wash`.
>
> The `remainder_bars` is correctly reported in the result but nothing acts on it.
>
> **Fix shape:** for `num_complete_cycles == 0`, schedule one partial cycle and clip, or fall
> back to the section's own duration. Either is a few lines.

**Census independently re-derived by AST against the current tree during spec authoring:
37 templates; `cycle_bars` 4.0 ×34, 8.0 ×1, 2.0 ×2 — exact match.** Re-verified:
`scheduler.py:92` computes `num_complete_cycles = int(duration_bars // contract.cycle_bars)`,
`:96` branches on `num_complete_cycles == 0`, `:104-105` returns the empty result.

### 2. Narrative templates play only their middle step (P4-F5). Verbatim:

> `schedule_repeats` instantiates steps exclusively from `contract.loop_step_ids`
> (`scheduler.py:116-130` via `_get_step_order`, `:206`). Steps defined on the template but
> absent from `loop_step_ids` are **never scheduled**. AST extraction over all 37 templates
> found exactly two with unscheduled steps:
>
> | template | steps defined | `loop_step_ids` | never rendered |
> |---|---|---|---|
> | `build_drop_recover` | build (2 bars), drop (2), recover (2) | `["drop"]` | **build, recover** |
> | `intro_main_outro_phrase` | intro (2), main (4), outro (2) | `["main"]` | **intro, outro** |
>
> `build_drop_recover` advertises `tags=["multi_step","build","drop","recover","transition"]`
> and `description` promising the arc; it renders a 2-bar `ACCENT_SNAP`/`PULSE` loop. …
> The `FADE_IN` and `FADE_OUT` dimmer steps in both — the only places in the whole library
> where a template shapes its own entry and exit — are dead.
>
> **Fix shape:** either author's error (`loop_step_ids` should list all three) or a scheduler
> that plays non-loop steps once at entry/exit. The former is a two-line data fix; a
> template linter would have caught it.

### 3. The 2× overrun (P4-F6). Verbatim:

> `schedule_repeats` computes `num_complete_cycles = duration_bars // contract.cycle_bars`
> (`scheduler.py:92`) but advances the schedule clock by the **sum of the loop steps' own
> `duration_bars`** (`:119-130`). Nothing checks that these agree. AST comparison across all
> 37 templates found one mismatch:
>
> - `split_lr_sweep_counter`: `cycle_bars = 4.0`, `loop_step_ids = ["left_sweep",
>   "right_sweep"]`, each step `duration_bars = 4.0` → **loop duration 8.0 bars per
>   "cycle"**.
>
> For a 16-bar section: `num_complete_cycles = 4`, scheduled span `4 × 8 = 32` bars. The
> segments run 16 bars past the section end. Its `remainder_policy` is `HOLD_LAST_POSE`
> (as with all 37), so `_clip_segments_to_boundary` (`template_compiler.py:211`) is **not**
> invoked — clipping only runs for TRUNCATE/FADE_OUT, which no template uses (P4-F21).
>
> **Fix shape:** validate `sum(step_durations[s] for s in loop_step_ids) == cycle_bars` at
> registration time (would also have caught P4-F5), and clamp the schedule to
> `duration_bars` regardless of remainder policy.

Related, and needed for the clamp (P4-F21, verbatim):

> the fade gate at `template_compiler.py:349` tests `channel_name.value == "DIMMER"` while
> `ChannelName.DIMMER.value == "dimmer"` (`models/enum.py:166`), so FADE_OUT would degenerate
> to a hard truncate even if selected. … Note the clipping code is also what P4-F6 needs, so
> repair rather than delete.

### 4. BLACKOUT renders full brightness (P4-M2, HIGH, verified numerically). Verbatim:

> Two independent bugs compose into a plan-triggerable inversion on exactly the templates a
> planner picks for drops.
>
> 1. `DimmerType.BLACKOUT` declares a single categorical entry —
>    `Intensity.SMOOTH: (min_intensity=0, max_intensity=0, period=1.0)`
>    (`libraries/dimmer.py:66-76`). For any other intensity the handler's guard
>    (`handlers/dimmers/default.py:85-89`) falls back to
>    **`DEFAULT_DIMMER_PARAMS[Intensity.SMOOTH]`**, i.e. `max_intensity = 128`
>    (`libraries/dimmer.py:35`) — the blackout's own `0` is discarded.
> 2. BLACKOUT's curve is `CurveLibrary.HOLD`, so it takes the static branch at
>    `handlers/dimmers/default.py:100-112`, calling
>    `_resolve_static_dmx_value(categorical_params.max_intensity, floor, ceiling)`. That
>    helper computes `value = int(normalized_value * 255)` (`:172`) — but `max_intensity` is
>    an **int in [0,255]**, not a normalized [0,1] value. So `128 × 255 = 32 640`, clamped to
>    the ceiling → **255**.
>
> Result, tracing the preset chain of P4-F8: CHILL→SLOW, ENERGETIC→DRAMATIC and
> INTENSE→FAST all miss the SMOOTH entry and render **DMX 255 — full brightness**. Only
> MODERATE→SMOOTH hits the blackout's own entry and yields `0 × 255 = 0`. The affected
> templates are `pop_lock_spotlight_blackout` and `spiral_xross_blackout`, whose
> `recommended_sections` are `drop, peak` and `drop, breakdown` — the planner will select
> them precisely where a blackout is the intended effect, and get the maximum-visibility
> opposite. Fix both halves together: the unit bug at `:172` and the fallback that discards a
> pattern's own semantics.
>
> (The same unit bug affects `DimmerType.HOLD`, whose SMOOTH entry is `max_intensity=255`;
> `255 × 255` also clamps to 255, which happens to be the intended "hold at full", so the bug
> is invisible there. It must still be fixed as part of the same change or HOLD will break.)

Re-verified: `handlers/dimmers/default.py:84-88` is the guard falling back to
`DEFAULT_DIMMER_PARAMS[Intensity.SMOOTH]`; `:173` is `value = int(normalized_value * 255)`;
`libraries/dimmer.py:66` is the `DimmerType.BLACKOUT` entry with `curve=CurveLibrary.HOLD`
(`:70`) and `DimmerType.HOLD` at `:77` with the same curve (`:81`).

### 5. Template dimmer floors are dropped (P4-M1, HIGH). Verbatim:

> All 37 templates declare `defaults={"dimmer_floor_dmx": 60, "dimmer_ceiling_dmx": 255}` —
> an explicit anti-flicker floor. `Template.defaults` is read at exactly one site,
> `compile/preset.py:118` (`new_defaults = deep_merge(template.defaults, preset.defaults)`),
> whose result is stored on the reconstructed `Template` at `:151` and **never read again**
> by any consumer (OBSERVED, exhaustive grep).
>
> The dimmer handler instead reads its floor from the *fixture calibration* dict
> (`handlers/dimmers/default.py:94-95,103-104`), which is populated in
> `fixture_builder.py:82-83` from `FixtureCalibration`, which the shipped path builds via
> `rig_profile_from_fixture_group(fixture_group)` (`pipeline.py:109`) — called **without**
> the optional `dimmer_floor_dmx` argument, so `rig.py:242` evaluates
> `dimmer_floor_dmx or 0` → **0**.
>
> Net: the template-declared floor of 60 is silently discarded and the effective floor is 0,
> so dimmers are driven fully to black rather than to the intended anti-flicker level. …
> Fix: either read `Template.defaults` in the compile context, or pass the floor through
> `rig_profile_from_fixture_group`.

Re-verified: `defaults={"dimmer_floor_dmx": 60, "dimmer_ceiling_dmx": 255}` present across
the builtin templates; `fixture_builder.py:82` reads
`fixture_def.calibration.dimmer_floor_dmx`.

**Note the interaction with P4-M2:** the floor and ceiling are the clamp bounds
`_resolve_static_dmx_value` uses. Fixing the unit bug without the floor leaves blackout at
0 (correct) but every other dimmer still bottoming out at 0 instead of 60; fixing the floor
without the unit bug leaves blackout clamped to the *ceiling*. **Both halves land here.**

### 6. Calibration is arithmetically annihilated (P4-F9, raised to HIGH). Verbatim:

> **[V] The one surviving use of the calibration is arithmetically annihilated, so the
> severity is HIGH, not MEDIUM.** The centre offset is
> `center_offset_normalized = (center - 0.5) * max_amplitude_norm * 1.0`
> (`handlers/movement/default.py:268`). Every `MovementCategoricalParams` in the library
> declares `center_offset = 0.5` — it is the field default (`libraries/movement.py:19-21`)
> and no pattern overrides it. So `(0.5 - 0.5) * max_amplitude_norm = 0` **identically**:
> the calibration-derived term is multiplied by zero at the only place it is consumed.
> Calibration has *no* effect on emitted DMX by any route.
>
> *Worked example.* A fixture calibrated to `tilt_min_dmx=110, tilt_max_dmx=145` (a narrow,
> physically-safe tilt window) with a base tilt at the centre of that window
> (`base_tilt_norm = 0.5`) and `Intensity.SMOOTH` (`amplitude = 0.4`):
> `desired_amplitude = 0.4 × 0.5 = 0.2` (`:301`); the excursion limits at `:308-310` are
> `1.0 − 0.5 = 0.5` and `0.5 − 0.0 = 0.5`, so `effective_amplitude = 0.2` — **the calibrated
> window never enters the calculation**. Output spans `0.5 ± 0.2` → normalized `[0.3, 0.7]` →
> **DMX 76.5–178.5**, against a calibrated safe range of `[110, 145]`. Nothing downstream
> re-clamps: `dimmer_curve_to_dmx` is the identity (above) and `ChannelValue.clamp_min/max`
> are left at `0`/`255`. On a physical moving head this is mechanical-limit exposure, not an
> aesthetic issue.

Also from P4-F9, the reason nothing downstream saves it:

> `step_compiler.py:198-227` also never passes `clamp_min`/`clamp_max`/`base_dmx`/
> `amplitude_dmx`, so `ChannelValue` defaults `0`/`255` apply (`channels/state.py:53-54`)
> and `dimmer_curve_to_dmx` computes `(0 + v·255)/255 = v` — **an identity function**.

Re-verified: `handlers/movement/default.py:268` is
`center_offset_normalized = (center - 0.5) * max_amplitude_norm * 1.0`.

### 7. Preset space (P4-F8). Verbatim (the part this task acts on):

> 5. Dimmer intensity survives, but `DEFAULT_DIMMER_PARAMS` (`libraries/dimmer.py:34-38`)
>    defines only `SMOOTH`, `DRAMATIC`, `INTENSE` — **no `SLOW`, no `FAST`** — and the
>    handler falls back to SMOOTH for anything missing (`handlers/dimmers/default.py:86-89`).
>
> Net: CHILL → SMOOTH dimmer; MODERATE → SMOOTH dimmer; ENERGETIC → DRAMATIC dimmer.
> `Intensity.INTENSE` dimmer params are unreachable from any prompt-offered value.
> **Two distinguishable outcomes.**

The prompt-side half (`user.j2:162` offering only CHILL/MODERATE/ENERGETIC, and the four
templates' unreachable `gentle`/`intense` presets) is **phase-3-owned and out of scope
here**; this task fixes the *renderer* half — the missing `SLOW`/`FAST` dimmer entries and
the fallback that discards a pattern's own semantics.

## Current behavior

- A 1-bar section renders **nothing** for all 37 templates; a 1–3-bar section renders
  nothing for 35 of 37.
- `build_drop_recover` renders a 2-bar `ACCENT_SNAP`/`PULSE` loop; `intro_main_outro_phrase`
  renders only its `SWEEP_LR`/`PULSE` middle. Every `FADE_IN`/`FADE_OUT` step in the
  library is dead.
- `split_lr_sweep_counter` schedules 32 bars into a 16-bar section with no clipping.
- `pop_lock_spotlight_blackout` and `spiral_xross_blackout` emit DMX 255 under CHILL,
  ENERGETIC and INTENSE; only MODERATE yields 0.
- Every dimmer floor of 60 is discarded; the effective floor is 0.
- Fixture calibration has no effect on emitted DMX by any route.
- `DEFAULT_DIMMER_PARAMS` has no `SLOW` or `FAST` entry.

## Target behavior

1. **Short sections render.** `num_complete_cycles == 0` schedules one instance scaled or
   truncated to the section's own duration. No section in a valid plan renders zero
   segments.
2. **Narrative templates play all their steps.** `build_drop_recover` renders
   build→drop→recover; `intro_main_outro_phrase` renders intro→main→outro. The `FADE_IN`
   and `FADE_OUT` dimmer steps reach the output.
3. **No section overruns.** The schedule is clamped to `duration_bars` regardless of
   remainder policy; `split_lr_sweep_counter` fits its section. A registration-time
   validator asserts `sum(step_durations[s] for s in loop_step_ids) == cycle_bars` and
   asserts every declared step is reachable, so F5 and F6 cannot recur.
4. **BLACKOUT is black under every preset.** The `int(normalized_value * 255)` unit
   confusion is fixed (`max_intensity` is already a DMX value in `[0,255]`), and the
   missing-intensity fallback preserves the pattern's own semantics rather than
   substituting `DEFAULT_DIMMER_PARAMS[SMOOTH]`. `HOLD` still holds at full.
5. **Dimmer floors are honored.** The template-declared `dimmer_floor_dmx`/
   `dimmer_ceiling_dmx` reach the dimmer handler's clamp.
6. **Calibration limits the output.** Emitted DMX for a calibrated axis stays inside the
   calibrated range. The `center_offset` term is no longer the sole (and zero-valued)
   consumer of the calibration.
7. `DEFAULT_DIMMER_PARAMS` covers all five `Intensity` members.

**Non-goals.** Do not widen the planner's `preset_id` vocabulary or edit prompts (phase 3
/ P2P). Do not fix `PING_PONG` (P4-F11), `FIGURE8` (P4-M7), the Lissajous straight lines
(P4-F12), or curve precision (P4-F10) here. Do not change the channel-default policy
(that is P1P-T6). Do not delete the clipping code — F6 needs it repaired.

## Implementation approach

Files/symbols to touch:
- `packages/twinklr/core/sequencer/moving_heads/compile/scheduler.py` — the
  `num_complete_cycles == 0` branch (`:96-107`), the step-order/schedule loop
  (`:114-130`), remainder handling (`:133-145`).
- `packages/twinklr/core/sequencer/moving_heads/compile/template_compiler.py` —
  `_clip_segments_to_boundary` (`:211`) invocation policy and the DIMMER case-mismatch
  gate (`:349`).
- `packages/twinklr/core/sequencer/moving_heads/templates/library.py` — registration-time
  validator (`TemplateRegistry.register` already materializes each template at `:52`, so
  the hook exists).
- `packages/twinklr/core/sequencer/moving_heads/templates/builtins/{build_drop_recover,
  intro_main_outro_phrase,split_lr_sweep_counter}.py` — data corrections if the chosen fix
  is data-side.
- `packages/twinklr/core/sequencer/moving_heads/handlers/dimmers/default.py` — the guard
  (`:84-88`), `_resolve_static_dmx_value` (`:155`, unit bug at `:173`), floor/ceiling
  sourcing (`:94-95,103-104`).
- `packages/twinklr/core/sequencer/moving_heads/libraries/dimmer.py` —
  `DEFAULT_DIMMER_PARAMS` (`:34`), the BLACKOUT/HOLD entries (`:66`, `:77`).
- `packages/twinklr/core/sequencer/moving_heads/compile/preset.py` — `Template.defaults`
  merge (`:118`, `:151`) and whatever carries it into the compile context.
- `packages/twinklr/core/sequencer/moving_heads/fixture_builder.py` (`:82-83`) and the
  `rig_profile_from_fixture_group` call (`pipeline.py:109`) for the floor plumbing.
- `packages/twinklr/core/sequencer/moving_heads/handlers/movement/default.py` (`:268`,
  `:301-330`) and `compile/step_compiler.py` (`:198-227`) for the calibration path.

Design decisions already made (do not relitigate):
- **P4-F5's fix is preferred as the data fix** (`loop_step_ids` lists all steps) *plus*
  the registration-time validator, per the review's "the former is a two-line data fix; a
  template linter would have caught it". If playing non-loop steps once at entry/exit is
  chosen instead, the validator must still land.
- **The schedule is clamped unconditionally**, not only for TRUNCATE/FADE_OUT.
- **P4-M2's two halves land together** (unit bug + fallback), and the HOLD case is
  explicitly re-tested because the unit fix changes its arithmetic even though its output
  is unchanged.
- **Calibration must bound the emitted value**, by whichever of the two available levers
  is cleaner: passing real `clamp_min`/`clamp_max` into `ChannelValue` at
  `step_compiler.py`, or applying the calibrated range in the movement handler's
  excursion limiting at `:301-330`. Do **not** "fix" it by making `center_offset`
  non-0.5 in the library — that changes choreography to work around an arithmetic bug.

Sequencing constraints (copied verbatim from `build/plan/00-overview.md`):

> `make validate` equivalents (check-only forms until P0-T4 lands the guard) must pass
> at every merge; golden tests (once P1P-T1 exists) must pass for any lane touching
> render/export code.

> **Verification currency**: evidence in specs is from baseline `aa8d325`. Executors
> must re-verify cited line numbers before editing (the tree will drift as phases land)
> — specs cite symbol + file, with line numbers as hints only.

From `build/plan/02-phase-1p-render-truth.md`:

> **Lane R (render repair, serial — shared files in `sequencer/moving_heads/` +
> `curves/`)**: T3 → T4 → T5 → T6.

## Acceptance criteria

- [ ] A 1-bar section renders **non-zero** segments for all 37 templates (today: zero for
      all 37). Parameterized test over the registry.
- [ ] A 3-bar section renders non-zero segments for all 37 templates (today: zero for 35).
- [ ] `build_drop_recover` renders segments derived from **all three** of its steps, and
      `intro_main_outro_phrase` from all three of its steps; at least one `FADE_IN` and one
      `FADE_OUT` dimmer curve appears in the golden output.
- [ ] `split_lr_sweep_counter` over a 16-bar section produces segments whose maximum
      `t1_ms` does not exceed the section end (today: 2× overrun).
- [ ] Registration-time validator rejects a template whose loop-step durations do not sum
      to `cycle_bars` and a template with an unreachable declared step; a unit test
      constructs both invalid templates and asserts the rejection. All 37 shipped
      templates pass the validator.
- [ ] `pop_lock_spotlight_blackout` emits **DMX 0** on the dimmer channel under
      `preset_id` ∈ {CHILL, MODERATE, ENERGETIC, INTENSE} — all four (today: 255 for three
      of them). Same for `spiral_xross_blackout`.
- [ ] `DimmerType.HOLD` still emits 255 at SMOOTH after the unit fix.
- [ ] With a template floor of 60, no emitted dimmer value for a non-BLACKOUT template
      falls below 60 (blackout is the documented exception and must be exempted
      explicitly, not accidentally).
- [ ] With `tilt_min_dmx=110, tilt_max_dmx=145` (the P4-F9 worked example, present in the
      P1P-T2 rigs), **every emitted tilt DMX value lies within [110, 145]** (today:
      76.5–178.5).
- [ ] `DEFAULT_DIMMER_PARAMS` contains entries for all five `Intensity` members.
- [ ] `make validate` check-only equivalents pass; golden suite regenerated with reviewed
      diffs.

**Golden-diff expectation (BEFORE/AFTER), deterministic plan incl. the 1-bar section and
the narrative template, on the narrow-calibration rig:**

```
BEFORE:
  - The 1-bar section contributes ZERO effects to the golden (empty region).
  - build_drop_recover contributes only ACCENT_SNAP/PULSE segments; no FADE_IN
    or FADE_OUT curve appears anywhere in the file.
  - split_lr_sweep_counter's last effect ends ~2x past its section end.
  - Blackout template's dimmer: E_SLIDER_DMX{dimmer}=255 under ENERGETIC.
  - Dimmer value curves reach 0.00 at their minima.
  - Tilt value-curve payloads span normalized [0.30, 0.70] -> DMX ~76..179,
    outside the rig's calibrated [110, 145].

AFTER:
  - The 1-bar section contributes effects (new block in the golden). This is the
    single largest structural diff in this task.
  - FADE_IN and FADE_OUT dimmer curves appear for the two narrative templates.
  - split_lr_sweep_counter's final t1_ms == section end.
  - Blackout dimmer: E_SLIDER_DMX{dimmer}=0 under every preset.
  - Non-blackout dimmer minima >= 60 (the declared floor).
  - Tilt payloads compressed into the calibrated window; emitted DMX min >= 110
    and max <= 145.
  - UNCHANGED: section start times (owned by P1P-T4 — any movement here means a
    merge/rebase error), movement intensity mapping (owned by P1P-T3), and the
    E_SLIDER_DMX zero-fill on unwritten channels (owned by P1P-T6).
```

## Tests

TDD: the 1-bar-section test, the blackout test, and the calibration-range test all fail
at baseline and are the cheapest to write first.

| Test | Behavior pinned |
|---|---|
| `test_one_bar_section_renders[template]` (×37) | P4-F4: no template renders silence for a 1-bar section |
| `test_three_bar_section_renders[template]` (×37) | P4-F4: the 35-of-37 case |
| `test_narrative_templates_render_all_steps` | P4-F5: build/recover and intro/outro reach the output |
| `test_schedule_never_exceeds_section[template]` (×37) | P4-F6: clamp holds for every template, not just the known-bad one |
| `test_registration_rejects_step_duration_mismatch` | The linter that makes F5/F6 unrepeatable |
| `test_registration_rejects_unreachable_step` | Same |
| `test_blackout_is_zero_under_all_presets[template,preset]` | P4-M2 half 1+2 |
| `test_hold_dimmer_still_full_at_smooth` | P4-M2's collateral (the unit fix must not break HOLD) |
| `test_static_dmx_value_treats_max_intensity_as_dmx` | P4-M2 unit bug, at the helper level |
| `test_template_dimmer_floor_reaches_output` | P4-M1 |
| `test_emitted_tilt_within_calibrated_range` | P4-F9, the worked example verbatim |
| `test_default_dimmer_params_covers_all_intensities` | P4-F8 renderer half |
| Golden suite (P1P-T1) | Reviewed BEFORE/AFTER diff as specified above |

## Verification commands

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy .

uv run pytest tests/unit/sequencer/moving_heads -v
uv run pytest tests/golden -v

# defect-specific checks the verifier runs
grep -n "int(normalized_value \* 255)" packages/twinklr/core/sequencer/moving_heads/handlers/dimmers/default.py  # expect: no match
grep -rn "DEFAULT_DIMMER_PARAMS\[Intensity.SMOOTH\]" packages/twinklr/core/sequencer/moving_heads/handlers      # expect: no semantics-discarding fallback
grep -n '"DIMMER"' packages/twinklr/core/sequencer/moving_heads/compile/template_compiler.py                    # expect: no case-mismatched comparison

# cycle_bars / loop-step census must still hold after any data edits
uv run python -c "
import ast,glob
from collections import Counter
c=Counter()
for f in glob.glob('packages/twinklr/core/sequencer/moving_heads/templates/builtins/*.py'):
    if f.endswith('__init__.py'): continue
    for n in ast.walk(ast.parse(open(f).read())):
        if isinstance(n,ast.Call) and getattr(n.func,'id','')=='RepeatContract':
            kw={k.arg:k.value for k in n.keywords}
            c[ast.unparse(kw['cycle_bars'])]+=1
print(sum(c.values()), dict(c))"   # expect: 37 {'4.0': 34, '8.0': 1, '2.0': 2}
```

No LOCAL-ONLY steps. No paid API calls.

## Effort & risk

**Effort: L** — seven findings, three subsystems (scheduler, dimmer handler, calibration
path).

**Main risk: the calibration fix (P4-F9) changes the look of every show on any rig with a
non-trivial calibration**, and the "right" compression of a wide curve into a narrow safe
window is a choreographic decision (clamp? scale? scale-and-recentre?). Mitigation: pick
**scale-and-recentre into the calibrated window** (preserves curve shape, guarantees the
bound) and state it in the code; the golden diff on the narrow-calibration rig makes the
result inspectable; the opus verifier reviews the choice explicitly. Rejected
alternative: hard clamp, which flattens the extremes into plateaus and looks like a
stuck fixture.

**Second risk: making short sections render could produce absurd output** — a 4-bar
pattern crushed into 1 bar is the same time-compression defect P4-F7 documents for
remainders. Mitigation: prefer *truncate to the section duration* over *scale the whole
cycle* for sections shorter than one cycle, and assert the resulting curve's rate is
within a factor of ~1 of the nominal step rate; record the choice in the spec's handoff.

**Third risk: unclamping/clamping interactions with P1P-T4's grid change** — both alter
segment boundaries. Mitigation: Lane R is serial (T3 → T4 → T5), so T5 rebases onto T4's
merged grid and regenerates goldens once, not twice.

## Backlog additions from P1P-T1 verification (2026-08-13, binding)

1. **NEW DEFECT owned by this task — transition segments emit all-zero settings:**
   `channel_blender.py` returns the blend on `ChannelValue(curve=...)` with
   static/base/value_points unset; `dmx_settings_builder._extract_channel_data`
   reads only those three and never `curve` — the blend is dropped and zero-fill
   writes 0 to all 16 channels for ~1s at every section boundary (validator missed
   it: transitions sit on layer 1). Pinned in
   tests/golden/test_transition_segments_emit_all_zero. **P1P-T6 is BARRED from
   "resolving" this via channel defaults** — defaults would flip the test green
   while the blend is still discarded; the fix is the compile→export contract
   (settings builder must consume `curve`).
2. **Golden coverage prerequisite:** the current golden plan fixtures do NOT
   exercise P4-M1 (dimmer floors) or P4-M2 (BLACKOUT inversion) — extend
   tests/golden/harness.py `build_plan()`/RIGS with a blackout section and a
   floor-declaring template (per the P1P-T2 extension note) BEFORE fixing M1/M2, so
   the fixes land as visible golden diffs.

3. **8-fixture rigs render NOTHING (P1P-T2 discovery, mechanism-verified):**
   `fixture_builder._infer_fixture_role` maps only 1-4 fixtures to spatial roles;
   larger rigs get positional names (ALL_0..ALL_7) matching no template role, and
   `compile_template`'s role filter silently skips every section (`continue`, no
   error). Pinned in tests/golden/test_8head_role_mismatch.py. Fix the silent-skip
   here (loud behavior + role-inference generalization or documented rig limits);
   P1P-T11's CLI rig-config work must surface unsupported rig shapes to the user.

4. **P4-F14 un-masked by T3's M5 fix (verifier-routed):** step_compiler's
   phase-shift with wrap=True now snaps mid-segment for curves that no longer
   close on their start value (9 of 108 golden curves gained a full-span interior
   jump; net discontinuities still improved 84→69 and 66 pre-date T3). Nothing
   tests the phase path — add a discontinuity pin and fix the wrap semantics here.
