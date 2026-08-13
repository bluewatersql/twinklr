# P2P-T2 — Renderer resolves schema v2

Phase: 2P (Creative Quality, Measured) · Lane: S (schema/channel, serial) · Executor: opus · Verifier: opus · Depends on: P2P-T1

## Objective

Make the widened plan contract reach the light. The template layer gains
parameterized color/shutter/gobo channel support mirroring the existing Dimmer
family; the categorical vocabulary is resolved by the renderer for the first time in
the repository's history; and schema-v2 intents compile to curves and DMX values with
fixture-declared defaults as the fallback. After this task, a plan that says
"chorus: INTENSE, palette role ACCENT, shutter strobe on the drop" produces different
emitted bytes than one that does not.

## Evidence & background

Findings: **P4-F16 / V1-extension** (color, gobo, shutter unwired end-to-end),
**P5-V1** (exporter forces shutter to 0 against the repo's own open=255 default),
**P4-F17** (V-categorical REFUTES — vocabulary never imported by MH rendering),
**CF-3**, **CF-7**.
Sources: `changes/twinklr-reactivation-review/reviews/phases/moving-heads-rendering.md`
P4-F16/F17/F20 §9, §7; `.../reviews/verification.md` "Phase 4" and "Phase 5"
(V1 STRENGTHENED).

Verified mechanics — quoted so the executor implements *this* design, not a variant:

**Already built and correct (do not rebuild):**
> the IR is channel-generic (`FixtureSegment.channels` is an open
> `dict[ChannelName, ChannelValue]`); the exporter already writes any mapped channel
> with correct inversion; fixture config already carries
> `color_channel`/`gobo_channel`/`shutter_channel` plus
> `color_map`/`gobo_map`/`shutter_map`/`shutter_default`
> (`config/fixtures/dmx.py:91-131`); `ColorLibrary` already defines 14 presets with
> DMX wheel positions (`libraries/color.py:26-41`) and `ShutterLibrary` 6 patterns.

`ChannelName.{COLOR,GOBO,SHUTTER}` (`models/enum.py:166-171`), the mapping in
`DmxSettingsBuilder._get_dmx_channel_number` (`:162-164`) and the inversion flags
(`:209-219`) "are all present and correct". **The export layer verifiably needs zero
changes.**

**Actually missing (the whole task, per P4-F16's assessment — "PARAMETER PLUMBING,
not structural redesign"):**
> 1. A fourth axis on `TemplateStep` (`models/template.py:328-337`) — e.g.
>    `color: Color | None`, mirroring `Dimmer`. **~40 LOC.**
> 2. A `ColorHandler` protocol + registry + default handler, mirroring
>    `DimmerHandler` (`handlers/protocols.py:169`, `handlers/registry.py:219`,
>    `handlers/dimmers/default.py`). **~250 LOC**, structurally identical to existing
>    code.
> 3. Three lines in `step_compiler.py` to emit the channel; one line in
>    `handlers/defaults.py:152` to register.
> 4. **Re-authoring 37 Python template files** — the real cost, and it is mechanical
>    but manual because templates are code (§7). ~37 × 10 lines.
> 5. Widening the planner contract: a color field on `PlanSection` and a prompt
>    section. Phase 3 seam.

Item 5 is done by P2P-T1. **Item 4 is deliberately deferred to P2P-T3** (data-first
loader) — see Non-goals. This task delivers items 1–3 plus the intent→DMX resolution
and the fixture-default fallback.

**The design question the review already answered:**
> a colour **wheel** is a discrete DMX index (`ColorPresetDefinition.dmx_value`,
> `libraries/color.py:62`), not a continuous curve, so colour changes are step
> functions with a mechanical settling time (`capabilities.py:44 color_change_ms`,
> currently unread). The `ChannelValue.static_dmx` branch already models exactly
> this. RGB-mixing fixtures would need three channels, which the current
> `DmxChannelMapping` does not model — but that is an additive config change.

So: **wheel channels resolve to `static_dmx` step values, not curves.** RGB mixing is
out of scope (additive config change, not this task).

**Vocabulary import is the first ever:**
> zero files under `sequencer/moving_heads/`, `core/curves/`, `sequencer/models/`, or
> `core/resolvers/` import `sequencer.vocabulary` at all.

Verified in-tree today. This task makes `sequencer/moving_heads/` a vocabulary
importer for the first time — a structural change reviewers should expect, not
flag.

**Dead layers that this task must consciously either revive or leave dead:**
`ChannelState` (`channels/state.py:215-357`, 143 LOC) is "a complete, unused
implementation of the runtime channel layer" mapping logical channels to DMX
including COLOR/GOBO/SHUTTER with inversion and clamping, with zero importers.
`get_max_channel` (`config/adapter.py:77`) computes the rig's true highest DMX
channel including shutter/colour/gobo and has zero callers, while the exporter
substitutes its own floor-16/round-to-16 rule (P4-F3). Decide explicitly: revive one
or both, or delete them in this task. Leaving a third channel-convention declaration
unread after this task is not acceptable — "All three declared conventions are
honoured nowhere" must stop being true.

Line numbers are hints from baseline `aa8d325`; re-verify before editing.

## Current behavior

- `step_compiler.py` adds exactly PAN, TILT, DIMMER to each `FixtureSegment`
  (verified in-tree: three `segment.add_channel(...)` calls) "and no other code path
  adds any". The shipped product choreographs three channels.
- The exporter zero-fills every unchoreographed DMX channel 1–16 including shutter
  (P4-F3 / CF-7), which by this repo's own constant means *closed*. P1P-T6
  (channel-default policy) changes zero-fill to fixture-declared defaults; this task
  layers plan-driven values on top of that policy.
- `ColorLibrary`, `GoboLibrary`, `ShutterLibrary` (643 LOC) have zero consumers —
  "not even a test imports them".
- No renderer code resolves any categorical vocabulary value.

## Target behavior

1. **`TemplateStep` gains color / shutter / gobo axes** alongside `dimmer`, typed and
   `extra="forbid"` like the rest of the model. Every axis is optional at the
   template level (`| None`) so the 37 existing builtins remain valid without
   re-authoring.
2. **Handler families for the new axes**, each mirroring the Dimmer family exactly:
   protocol in `handlers/protocols.py`, registry entry in `handlers/registry.py`,
   default implementation under `handlers/{colors,shutters,gobos}/default.py`,
   registration in `handlers/defaults.py`.
3. **`step_compiler` emits the new channels** via `segment.add_channel(...)` with
   `static_dmx` for wheel positions, and curve points only where the axis is
   genuinely continuous (e.g. a shutter strobe rate expressed as a repeating value
   curve, if the chosen encoding supports it).
4. **Schema-v2 intent resolution.** A resolution layer maps `PlanSection` v2 intents
   to template-step parameter overrides:
   - categorical intensity → the movement/dimmer parameter tables already keyed by
     `Intensity` (`libraries/movement.py`, `libraries/dimmer.py`);
   - `ColorIntent` (palette role or explicit cue) → a `ColorLibrary` preset →
     `dmx_value`;
   - shutter/gobo events → timed `static_dmx` step values placed against the beat
     grid (the ONE grid from P1P-T4 — see sequencing constraint below).
5. **Fixture-default fallbacks.** When the plan expresses no intent for an axis, or
   the resolved intent names something the rig cannot do (channel not mapped, preset
   absent from `color_map`), the renderer falls back to the fixture's declared
   default (`shutter_default`, the map's identity entry) and records the fallback in
   the render trace — never silently to zero. This is the CF-7 lesson: an unwritten
   channel and a channel written to 0 are different things.
6. **One channel-convention authority.** `get_max_channel` and/or `ChannelState` is
   either wired in or deleted, with the decision written into the module docstring.

### Non-goals

- **Re-authoring the 37 Python templates to use the new axes.** P4-F16's conclusion:
  "the bulk is template re-authoring, which argues strongly for the data-first
  template loader recommended in §7 — do that first and the 37-template re-authoring
  becomes a data edit rather than 37 Python diffs." P2P-T3 lands the loader; template
  content migration happens there or later. This task adds the capability and proves
  it on **2–3 templates** (see acceptance criteria), not 37.
- Export-layer changes (verified unnecessary).
- RGB-mixing fixtures (`DmxChannelMapping` does not model three-channel colour).
- Display-side rendering.

## Implementation approach

Files/symbols (re-verify first):

- `packages/twinklr/core/sequencer/models/template.py` — `TemplateStep` (new axes),
  the axis models mirroring `Dimmer`.
- `packages/twinklr/core/sequencer/moving_heads/handlers/protocols.py`,
  `handlers/registry.py`, `handlers/defaults.py`, new
  `handlers/{colors,shutters,gobos}/`.
- `packages/twinklr/core/sequencer/moving_heads/compile/step_compiler.py` — the
  `segment.add_channel` block (currently PAN/TILT/DIMMER).
- `packages/twinklr/core/sequencer/moving_heads/libraries/{color,gobo,shutter}.py` —
  now consumed for the first time; keep, per P4-F20's "keep if option (c) is chosen".
- `packages/twinklr/core/sequencer/moving_heads/pipeline.py` —
  `TemplateCompileContext` widens beyond the five fields (P4-F23) to carry the
  resolved intents.
- `packages/twinklr/core/config/fixtures/dmx.py`, `config/adapter.py::get_max_channel`
  — read, not rewritten.
- `packages/twinklr/core/sequencer/vocabulary/` — imported by the renderer for the
  first time.

Sequencing constraints copied verbatim from the plan:

> - **Verification currency**: evidence in specs is from baseline `aa8d325`.
>   Executors must re-verify cited line numbers before editing (the tree will drift
>   as phases land) — specs cite symbol + file, with line numbers as hints only.
> - `make validate` equivalents (check-only forms until P0-T4 lands the guard) must
>   pass at every merge; golden tests (once P1P-T1 exists) must pass for any lane
>   touching render/export code.
> - CF-2 grid fix spans agents-context (`_ms_to_bar`) and sequencer — one task, both
>   halves (P1P-T4).

Consequences of that last one for this task: **event placement uses the BeatGrid
consumers fixed by P1P-T4, never a re-derived average `ms_per_bar`.** Do not
reintroduce a uniform-average grid for shutter/gobo event timing. P2P-T8 may later
change the grid's *source*; this task must be indifferent to that.

Also inherited: P1P-T6 established the channel-default policy (fixture-declared
defaults instead of zero-fill). This task must compose with it, not replace it: plan
intent wins over fixture default, fixture default wins over zero.

## Acceptance criteria

1. `TemplateStep` carries color/shutter/gobo axes; all 37 existing builtins still
   construct and register without modification.
2. A `ColorHandler`/`ShutterHandler`/`GoboHandler` protocol + registry + default
   handler exists for each axis, registered in `handlers/defaults.py`, following the
   Dimmer family's shape.
3. `step_compiler` emits COLOR/SHUTTER/GOBO channels into `FixtureSegment` when the
   compiled step carries them.
4. The renderer imports `sequencer.vocabulary` (first time) and resolves the
   schema-v2 intents through it; `Intensity`-keyed parameter lookup is unchanged
   from the P1P-T3 repair.
5. **Golden-diff BEFORE/AFTER, explicit:**
   - *No-intent plan* (schema v2 with all intent fields null): emitted settings
     strings are **byte-identical** to the P1P-T6 baseline. Widening the contract
     must not move existing output.
   - *Color-intent plan* on a rig whose `color_channel` is mapped inside 1–16:
     AFTER contains an `E_SLIDER_DMX<color_channel>` entry with the
     `ColorLibrary` preset's `dmx_value`; BEFORE contains the fixture default (or,
     pre-P1P-T6, zero).
   - *Shutter strobe intent* on the shutter-channel=6 rig from the P1P-T1 fixture
     set: AFTER emits the strobe pattern's DMX on channel 6; on the
     shutter-channel=17 rig (outside the 1–16 window) the intent is **dropped with a
     recorded trace warning**, and the emitted bytes are unchanged — the
     counter-evidence case the review flagged (V1's "the only in-repo fixture config
     uses shutter_channel=17").
   - *Unmappable preset* (a colour the rig's `color_map` lacks): output falls back to
     the fixture default and the trace records the fallback; output is never 0
     unless 0 is the declared default.
6. The existing 587-LOC validator (`scripts/validation/_core/mh_xsq_validation.py`),
   wired into CI by P1P-T1, passes on the new artifacts — including its
   shutter/colour/gobo cross-checks against the fixture map (`:414-416`, `:452-454`),
   which now have real content to check for the first time.
7. `get_max_channel` / `ChannelState` are wired or deleted, decision documented.
8. `make validate` check-only forms pass.

## Tests

TDD — failing first:

1. `test_step_compiler_emits_color_channel` / `_shutter_` / `_gobo_` — a compiled
   step with each axis produces the corresponding `ChannelName` entry in the
   `FixtureSegment` with the expected `static_dmx`.
2. `test_wheel_channels_are_step_functions_not_curves` — pins the design decision:
   a colour intent produces `static_dmx`, never a `PointsCurve`.
3. `test_intent_resolution_falls_back_to_fixture_default` — unmapped channel and
   absent preset both produce the declared default plus a trace entry, not 0.
4. `test_shutter_channel_outside_window_is_dropped_not_emitted` — the =17 rig case.
5. `test_no_intent_plan_is_byte_identical` — golden, criterion 5 bullet 1.
6. Golden settings-string tests for the 2–3 templates migrated to carry real axes.
7. `test_renderer_imports_vocabulary` is **not** a useful test — instead assert the
   resolved behavior (an `Intensity`/palette-role value changes emitted DMX).

## Verification commands

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy .
uv run pytest tests/unit/sequencer tests/integration -q
uv run pytest -k golden -q
uv run python scripts/validation/validate_artifacts.py <generated-artifact-dir>   # existing 587-LOC validator
```

No paid API calls. xLights visual confirmation of colour/shutter output is
**LOCAL-ONLY** and belongs to P2P-T5/T12, not here.

## Effort & risk

**L.** Main risk: this is the first task that makes previously-dead libraries live,
so their latent defects surface all at once (the review found e.g. three colliding
casing conventions in the also-dead `resolvers/poses.py` — treat every revived
library as unproven). Mitigation: revive one axis at a time (shutter first — it has
the smallest vocabulary, a declared default, and an existing validator cross-check),
land each behind its own golden test, and require the byte-identical no-intent case
to pass after every axis. Second risk: scope creep into the 37-template re-authoring
— explicitly out of scope here; migrate 2–3 templates only, as capability proof.
