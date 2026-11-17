---
type: review
status: complete
area: engineering
change: 2026_11_12_mh_true_up
created: 2026-11-16
updated: 2026-11-16
---

# `twinklr show` on the physical renderer (C1.1a) — 2026-11-16

Cutover step C1.1a: `twinklr show` renders moving heads on the physical renderer, so
the legacy renderer can later be removed (C1.2). Built on `feat/mh-cutover-show` from
`b5cbc658`, reviewed once (approve with fixes) and reworked. Everything here is
offline and synthetic: no provider request, no owner-local data, no xLights.

## Design

- **The pipeline.** A `physical_v2` show checks the rig when it loads, admits the
  physical family catalog, offers only physical templates, and runs the moving-head
  render preflight gate right after audio analysis, before any planner. To do that the
  show's shared prefix is now the moving-head definition's. The layout's models reach
  the gate and the render through pipeline state. `CombinedShowRenderStage` dispatches
  once on the mode: `_render_physical`, or `_render_legacy` (deleted in C1.2).
- **Coordination becomes darkness.** `moving_head_dark_spans`
  (`sequencer/show_coordination.py`) turns the coordination schedule's rests for the
  moving heads into spans: the time of each macro section that no window activates a
  moving-head target in. These are the other team's call/response turns, and sequenced
  or ripple steps on other targets.
  - Spans are computed inside macro sections only. Time outside every macro section is
    not rested.
  - `RenderingPipeline(dark_spans=...)` snaps each span outward to the 20 ms frame grid,
    then applies the limits of `_span_limits`, which mirror what the transaction pass's
    shutter timing check requires. For a head that goes dark through its shutter, each
    span is lengthened to the closed state's close latency plus settle, and spans that
    leave less than the open latency plus the lit states' settle between them are
    merged. A head that goes dark through a dimmer whose zero extinguishes has no such
    timing. Any rig is relit for at least two frames. Spans are rig-wide, so the
    slowest profile sets both limits, as for every fixture.
  - Through the shutter, a lit remainder of a cue between a span and the cue's own start
    or end shorter than the shutter needs to open is kept dark too.
  - The trace records the spans, as lengthened and merged, as `dark_spans`. They enter
    render identity only when there are any.
- **A cue keeps playing through a span, dark** (`_dark_over_spans`, `pipeline.py`).
  - A cue a span covers keeps every channel as compiled except the one its profile goes
    dark through: the dimmer at zero when the profile declares that zero extinguishes,
    else the profile's closed shutter. The cue's pose, zoom and wheels play on as
    authored.
  - This happens per section, before `_enter_section` and `plan_prepositions`. The final
    feasibility pass therefore sees the final visibility, just as it sees a visibility
    envelope's.
  - The head never leaves its authored path. It is where the music puts it when a span
    ends, so no re-entry window and no repositioning transaction follow a span.
  - A different cue after a span (a new section or step) is entered and reached exactly
    as it would be without the span. Entry windows exist only at section starts, as
    before, so no record or log line describes anything after a span as a "section".
- **What is not projected.** The macro palette and focal role (`coordinate_moving_head_plan`)
  are not applied on the physical path, because nothing there reads them. The render
  record's diagnostics say so with one `unsupported_attribute` warning per macro
  section.
- **Export** (`cli/show_cmd.py:export_show_artifacts`).
  - Output budgets: `max_effects` counts the moving heads' frame runs. `max_xsq_bytes`
    counts the whole combined `.xsq`, display effects included.
  - Both budgets are checked before anything is published. The `.xsq` and its trace are
    then published together, `.xsq` last, through `twinklr run`'s helper
    (`delivery.publish_files`).
  - The trace carries the physical render record with its `output` measure, as
    `twinklr run`'s does.
- **Evaluation.**
  - The show trace contract accepts the `render` record. It accepts an empty section and
    template only for a physical park (both empty, every source a `…/park/preposition`).
  - Show metrics read a physical trace's moving heads as onsets (`show_emissions`). Dark
    transaction and park runs, and runs starting inside a recorded dark span, are left
    out; consecutive runs with the same representative source merge into one onset.

## Frame evidence

All of the following is asserted on encoded frames: the renderer's own frames, or the
DMX effects decoded from the combined sequence.

- **In every span:** every head is commanded dark. Where a cue plays through the span,
  only the bytes the profile goes dark through differ from the plain render (the same
  plan with no spans), so pose, zoom and wheels follow the cue's authored trajectory.
  Where a section's entry window drops a cue inside a span, a dark transaction
  repositions the head there instead, so pose and wheel bytes can differ from the plain
  render; those frames are dark and honest. The reviewer saw this with the flick under
  60/40 ms latencies.
- **Outside the spans:**
  - Every lit frame is the plain render's frame.
  - No lit frame of the plain render is lost.
  - On the default rig, every byte is identical, including the entry records.
- **Honesty:** replanning the render's own cues gives the render's segments, and
  `assert_honest_transactions` passes on every fixture. No head is lit while it moves or
  turns a wheel, nor revealed before it settles.
- **Where it is covered:**
  - Unit tests (`tests/unit/sequencer/moving_heads/compile/test_dark_spans.py`): a cue
    crossing a span, a 40 ms span, a cue wholly inside a span, a different section's cue
    after a span, `drop_accent` and `preserve_aim` jobs, and a rig dark only through its
    shutter. The span limits are also covered:
    - one-frame gaps are merged and two-frame gaps kept;
    - on a dimmer rig with 200/200 ms latencies, the 380 ms answers of 150 BPM stay lit
      and a 40 ms span is not lengthened;
    - on a shutter rig with 40 ms open latency and 20 ms open settle, a 40 ms gap is
      merged and a 60 ms gap kept;
    - the reviewer's 60 ms close latency with 30 ms closed settle lengthens a 15 ms span
      to 100 ms under both `on_unplayable` settings, with nothing dropped;
    - a span ending 20 ms before its cue keeps the remainder dark, with no entry window
      opened and nothing dropped.
  - Integration tests through the real combined pipeline
    (`tests/integration/test_combined_show_physical.py`): call/response under `error`,
    `drop_accent` and `preserve_aim`, and a two-section show (call/response verse,
    unified chorus on another template).
- **Planning before painting:** a mutant that paints the spans onto the frames after
  planning fails on a frame assertion ("MH1 is lit at 2000 ms in a span"). It fails in
  the test where a span ends just before its cue does: the dark remainder is planned,
  not painted.
- **The reviewer's one-frame flash** (section `a` 15–2545 ms with the heads answering,
  then `b` opening with a call): frame 2520 is now dark on both heads, inside the merged
  span 2000–3020.

## Lit frames lost outside spans, before and after the rework

The scenario is a 1-beat call/response in which the heads answer the tree. It runs at
120 BPM over four bars, on a two-head family rig (topology plus the `flick` preset),
for the six zoomless families. Speeds are pan/tilt travel. "Lost" counts frames lit in
the plain render and dark in the show, outside the spans. The script reuses the reviewer's harness and
lives in the session scratchpad (`c11a/table.py`); it is not committed.

| Family | Speed | Fallback | Lit lost before | Lit lost after | Lit outside spans after | Lit where the plain render is dark, before / after | Honest after |
|---|---|---|---|---|---|---|---|
| `finite_snap_hold` | 150°/s | `error` | 0 | 0 | 384 | 0 / 0 | yes |
| `fly_in_cascade` | 150°/s | `error` | 0 | 0 | 0 | 0 / 0 | yes |
| `fly_out_cascade` | 150°/s | `error` | 0 | 0 | 192 | 0 / 0 | yes |
| `masked_wheel_flick` | 150°/s | `error` | 0 | 0 | 288 | 0 / 0 | yes |
| `mirror_wings` | 150°/s | `error` | 0 | 0 | 384 | 0 / 0 | yes |
| `target_orbit` | 150°/s | `error` | 0 | 0 | 384 | 0 / 0 | yes |
| `finite_snap_hold` | 150°/s | `drop_accent` | 0 | 0 | 384 | 0 / 0 | yes |
| `fly_in_cascade` | 150°/s | `drop_accent` | 0 | 0 | 0 | 0 / 0 | yes |
| `fly_out_cascade` | 150°/s | `drop_accent` | 0 | 0 | 192 | 0 / 0 | yes |
| `masked_wheel_flick` | 150°/s | `drop_accent` | 0 | 0 | 288 | 0 / 0 | yes |
| `mirror_wings` | 150°/s | `drop_accent` | 192 | 0 | 384 | 0 / 0 | yes |
| `target_orbit` | 150°/s | `drop_accent` | 0 | 0 | 384 | 0 / 0 | yes |
| `finite_snap_hold` | 90°/s | `error` | 0 | 0 | 336 | 0 / 0 | yes |
| `fly_in_cascade` | 90°/s | `error` | 0 | 0 | 96 | 0 / 0 | yes |
| `fly_out_cascade` | 90°/s | `error` | 0 | 0 | 96 | 0 / 0 | yes |
| `masked_wheel_flick` | 90°/s | `error` | 0 | 0 | 264 | 24 / 0 | yes |
| `mirror_wings` | 90°/s | `error` | 0 | 0 | 336 | 48 / 0 | yes |
| `target_orbit` | 90°/s | `error` | 0 | 0 | 336 | 0 / 0 | yes |
| `finite_snap_hold` | 90°/s | `drop_accent` | 144 | 0 | 336 | 0 / 0 | yes |
| `fly_in_cascade` | 90°/s | `drop_accent` | 0 | 0 | 96 | 0 / 0 | yes |
| `fly_out_cascade` | 90°/s | `drop_accent` | 0 | 0 | 96 | 0 / 0 | yes |
| `masked_wheel_flick` | 90°/s | `drop_accent` | 96 | 0 | 264 | 24 / 0 | yes |
| `mirror_wings` | 90°/s | `drop_accent` | 192 | 0 | 336 | 48 / 0 | yes |
| `target_orbit` | 90°/s | `drop_accent` | 144 | 0 | 336 | 0 / 0 | yes |

- **Why frames were lost before.** The first design cut cues at each span and re-entered
  the stretch after it through an entry window. Under a declared fallback the last cue
  was substitutable, so a window always opened, often for the whole response beat.
- **The "lit where dark" column.** Before, re-entry could also light a head where the
  plain render keeps it dark. After, the show's lit frames are the plain render's.
- **Lit counts below 384.** These come from the plain render itself. The cascades are
  dark much of the time by design, and some heads at 90°/s enter the first section
  through a window.

## Show metrics on a physical trace

These figures come from a call/response physical show written end to end by
`twinklr show` (8 display effects, 804 moving-head frame runs).

| | Before (reviewer) | After |
|---|---|---|
| Sync effects counted | 806 (about 200 per bar) | 24: 8 display, 16 moving-head onsets (2 heads × 8 answers) |
| Moving heads' section start | a dark transaction run | 520 ms, their first lit onset |
| Call/response pairs | every 20 ms run a candidate | each response observed at its window's first frame (515 → 520 ms, …) |

Hand-computed expectations on a small physical trace are in
`tests/unit/reporting/evaluation/test_show_metrics_physical.py`. Legacy metrics tests
are unchanged and pass.

## Pre-existing bug: the show's evaluation manifest refused real layouts

Since `3629fa90` (2026-11-12), `layout_to_choreography` maps every zone its groups lie
in to the group covering it, so a plan may target the zone. Every group lies in a zone,
so nearly every real layout gains such an alias: a group named "Yard Arches" gives
`YARD`.

- **Symptom.** `ShowEvaluationManifest` required the mapping ids to equal the graph's
  group ids. `twinklr show` therefore wrote its `.xsq` and trace, then exited 1 ("xLights
  mapping must cover every choreography graph group exactly once"). Legacy and physical
  shows were both affected; the reviewer reproduced it on the base commit.
- **Where it was fixed.** The aliases are intended at the source, because display
  rendering resolves zone targets through them, so the fix is in the two consumers
  (commit `26c70c48`):
  - the manifest admits mapping ids that are the graph's zone tags;
  - show metrics skip alias entries when they map element names back to groups.
    Relaxing the manifest alone made metrics raise "maps to multiple choreography ids".
- **Tests.** On a layout with a "Yard Arches" group, a legacy and a physical
  `twinklr show` both exit 0 with a valid manifest. Show output bytes are unchanged by
  the fix.

## What did not change

- **Legacy shows.** Through the real stage, call/response and unified shows are
  byte-identical to `b5cbc658`, both the `.xsq` and the trace. The new export writes the
  same files as the old one. Goldens and regression files are unchanged:
  `git diff --stat b5cbc658 -- tests/golden tests/regression` is empty.
- **Physical output without spans.** The gate scratchpad's 360-configuration byte
  matrix was run on `b5cbc658` and on this branch: 13,770 leaf comparisons, 0
  differences. The standalone fingerprint is unchanged when no span is given. The
  Phase 1 fingerprints hold: `60e0d5eb…11c7` and `b40905ec…cc86`.

## Item 9: can spans make a render fail after paid planning?

There is no longer any entry after a span, so `worst_case_entry_ms` is never asked
about one. Spans are known only after macro planning, so any refusal they cause comes
after paid requests.

- **Dimmer rigs.** On a rig whose dimmer at zero extinguishes, darkening adds no shutter
  change and no new refusal.
- **Shutter-only rigs.** In the first rework, a span shorter than the closed state's
  close latency plus settle failed the shutter timing check. The cue through it was kept
  dark under `on_unplayable: dark`, and the render was refused after planning under
  `error`. The reviewer reproduced this as 198 lit frames lost on one 2 s cue.
  - **Decision and fix.** Per the integrator's decision, spans are now lengthened to that
    time; lit gaps and cue-edge remainders shorter than the shutter needs to open are
    kept dark.
  - **Tested.** The reviewer's case renders with nothing dropped under both settings.
    Their second scenario set (91 scenarios) was rerun:
    - 90 render honestly, with no lit frame in a span and none lost outside one;
    - the 91st (`slow_rig_140bpm`) is refused by the gate before planning, as it was
      before this fix.
  - **What remains.** A cue whose own shutter changes fall closer to a span's edge than
    the shutter needs can still be kept dark or refuse. That is reasoned from the code;
    no test covers it.
- **Profiles that cannot go dark.** `_dark_over_spans` refuses a profile that declares no
  darkness a cue can command. That case is unreachable, because the gate's transactions
  already need such a darkness.

## For C1.2 to delete

**`pipeline/show_stages.py`:**
- `_render_legacy`;
- the `legacy = ... mode == "legacy_v1"` dispatch;
- the imports of `coordinate_moving_head_plan` and `coordinate_moving_head_segments`;
- the `available_templates` parameter and `self._available_templates` (used only by the
  legacy projection), and the argument that passes it in `definitions/show.py`;
- the `coordinated_mh_plan` state.

**`sequencer/show_coordination.py`:**
- `coordinate_moving_head_plan`, `coordinate_moving_head_segments`,
  `_macro_sections_for_emitted_id`, `_closest_preset`, `_PRESET_RGB`,
  `_ROLE_MH_INTENSITY`, and the imports only they use;
- their tests in `tests/unit/sequencer/test_show_coordination.py`.

**Legacy show tests:** `tests/integration/test_combined_show_pipeline.py`, and
`tests/integration/test_show_command_legacy_layout.py` (which a physical rig could
replace). The combined-show golden and its fixtures are owner-gated (F9).

**`cli/show_cmd.py`:** in `export_show_artifacts`, the implicit legacy branch
(`if record is not None`) becomes unconditional, and `render_record` and
`moving_head_runs` become required.

**`reporting/evaluation/show_metrics.py`:** in `show_emissions`, the
`trace.render is None` return. Every show trace then carries a render record, which
`ShowTraceV2.render` may then require.

**Reviewer's addition:** move the layout model check into
`prepare_combined_show_pipeline`, unconditionally. Today it runs in the gate through
state because doing it in the CLI would need a mode branch.

**Outside these files:** the legacy early return in `RenderPreflightStage`, and the
legacy `dmx_mapping` channel listing in `definitions/show.py` (C1.3).

## For the owner

- **Optical edges lag the beat.** Optical darkness lags a span's start by the
  profile's close latency, and the relight lags its end by the open latency. Spans are
  dark in encoded bytes, and the head stays on its authored path throughout, so no
  off-path motion shows during either lag.
  - **Option, not built:** command the dark edge earlier by the close latency and the
    relight earlier by the open latency, so that the optical edges land on the beat.

## Not verified

- The owner's rig, audio and layout; anything in xLights, including playback of a
  combined physical show.
- The zoom family under spans: the table's rig has no zoom axis.
- A real rig dark only through its shutter.
- Show metrics on cues that a visibility envelope darkens inside their own content: the
  trace does not record that darkness.
