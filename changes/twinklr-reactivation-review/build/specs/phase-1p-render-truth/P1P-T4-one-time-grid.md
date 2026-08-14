# P1P-T4 — One time grid

Phase: 1P (Render Truth) · Lane: R (render repair, serial) · Executor: opus · Verifier: opus · Depends on: P1P-T3

## Objective

Make the effects land where the timing marks say they should. Today three incompatible
time grids coexist: the planner floors section starts against a nominal tempo, the
renderer places effects on a song-wide *average* bar duration anchored at 0 ms, and the
timing tracks written into the same `.xsq` use the actual detected downbeats. The user
opens the sequence, sees the bar markers on the beat, and sees the moving-head effects
offset from them. This task replaces all three with the real `BeatGrid`.

**Both halves — planner-side `_ms_to_bar` and renderer-side `_bar_to_ms` — land in one
task. This is a hard constraint (see "Sequencing constraints").**

## Evidence & background

Findings: **CF-2** = **P4-F2** (CRITICAL) + **P4-M3**. Verifier verdict: *"F2 (CRITICAL,
held, extended): THREE grids, not two … Fix site spans phases 3+4."*

Line numbers are hints from baseline `aa8d325`. Re-verify before editing.

### The three grids (P4-F2, verbatim):

> **[V] Three grids coexist, not two.** The original report identified grids A and B; the
> verifier found a third that sits *upstream* of both and compounds the error.
>
> *Grid 0 (the plan's bar numbers) — phase 3's code.* The section boundaries the planner is
> given, and therefore the `start_bar`/`end_bar` the renderer receives, are produced by
> `MovingHeadContext._ms_to_bar` (`agents/sequencer/moving_heads/context.py:246-271`, called
> at `:194-195`). It converts with a **nominal tempo** (`self.tempo`, or a hard-coded 120 BPM
> fallback at `:258-259`), anchored at 0 ms, and **floors**:
> `bar_number = int(beat_number / beats_per_bar) + 1` (`:269`). The floor quantizes every
> section start *down* to a bar boundary — an error of up to one full bar, ≈2 s at 120 BPM
> in 4/4. So a chorus detected at 47.3 s is handed to the planner as a bar whose start the
> renderer will place at 46 s.
>
> *Grid A (effects).* `TemplateCompileContext._bar_to_ms` (`models/context.py:132`):
> `int((bar - 1) * self.beat_grid.ms_per_bar)`. `BeatGrid.ms_per_bar`
> (`timing/beat_grid.py:189-201`) is `(bar_boundaries[-1] - bar_boundaries[0]) /
> (len(bar_boundaries) - 1)` — **a single song-wide average**. Every section start, every
> step start, and every transition boundary
> (`compile/transition_detector.py:69`, same formula) derives from it, anchored at 0 ms.
>
> *Grid B (timing tracks).* `formats/xlights/sequence/timeline.py:128` writes a "Twinklr
> Bars" marker at each `beat_grid.bar_boundaries[i]` and `:104` a "Twinklr Beats" marker at
> each `beat_boundaries[i]` — the **actual detected** positions from librosa analysis
> (`BeatGrid.from_song_features` → `from_resolver`, `beat_grid.py:125,47`; this is the
> shipped construction path, called at `agents/sequencer/moving_heads/stage.py:136`).
>
> Both are written by `export_to_xsq` into the same `.xsq` (`xsq_export.py:77-84` for tracks,
> `:88-101` for effects).

### The divergence (verbatim):

> Grid 0 → Grid A contributes a quantization error of up to one bar (≈2 s at
> 120 BPM) on every section start, *before* Grid A → Grid B contributes
> `bar_boundaries[i] - i·avg_ms_per_bar`: (a) a **constant offset** equal to
> `bar_boundaries[0]` — the time of the first detected downbeat, non-zero for essentially
> every real recording (intro silence, pickup bar) — plus (b) accumulated **drift** wherever
> the tempo is not perfectly constant. The errors do not cancel; they are independent. The
> user opens the sequence in xLights, sees the bar markers on the beat, and sees the
> moving-head effects offset from them.

### The aggravating evidence (verbatim):

> **[V]** `BeatGrid.snap_to_nearest_bar` (`beat_grid.py:252`) exists precisely for this and
> its docstring reads *"Critical for precise beat synchronization — ensures effect timing
> aligns exactly with bar boundaries even if LLM-generated times are slightly off."*
> Corrected from the original report: it has **zero callers repo-wide** — the sole reference
> is one intra-class call from another `BeatGrid` method (`beat_grid.py:344`); no consumer
> anywhere invokes it. `get_bar_start_ms` (`:218`) has **zero callers of any kind**. …
> And `models/context.py:113-115` documents the *opposite* of what the code does:
> *"Uses detected beat boundaries to stay synced with actual music, not tempo-based
> calculation which can drift."*

### The prescribed fix shape (verbatim — do not substitute a different design):

> **Fix shape — spans two phases. [V]** Phase 4 side: route `_bar_to_ms` through
> `beat_grid.get_bar_start_ms(bar - 1)` with a bounds fallback to the average for bars past
> the detected range. Phase 3 side: `_ms_to_bar` must round to the *nearest* detected
> downbeat rather than flooring against a nominal tempo — ideally by taking the same
> `BeatGrid` the renderer uses instead of a scalar tempo. Fixing only the phase-4 half leaves
> the ≤2 s quantization in place, so the two must be sequenced together.

Re-verified in the current tree: `BeatGrid.ms_per_bar` (`beat_grid.py:189`),
`get_bar_start_ms` (`:218`), `snap_to_nearest_bar` (`:252`) all present;
`TemplateCompileContext._bar_to_ms` at `sequencer/models/context.py:118`;
`MovingHeadContext._ms_to_bar` at `agents/sequencer/moving_heads/context.py:246` with the
`tempo = 120.0` fallback at `:257`, `beats_per_bar = 4` default at `:261`, and
`bar_number = int(beat_number / beats_per_bar) + 1  # 1-indexed` at `:271`.
`timeline.py` still builds `"Twinklr Beats"` (`:114`) and `"Twinklr Bars"` (`:137`) tracks.

**Note on scope (from the phase plan):** *"NOTE: P2P-T8 (MIR adoption) upgrades the grid's
SOURCE; this task fixes the CONSUMERS."*

## Current behavior

- Planner receives section bars computed from a nominal tempo (120 BPM if unknown),
  anchored at 0 ms, floored to the bar below.
- Renderer converts those bars back to milliseconds as `(bar - 1) × ms_per_bar` using one
  song-wide average, anchored at 0 ms.
- Timing tracks in the same file use the detected per-bar boundaries.
- `snap_to_nearest_bar` and `get_bar_start_ms` — the methods written for exactly this —
  have zero callers.
- Transition boundaries (`compile/transition_detector.py`) repeat the average-grid
  formula independently.

## Target behavior

- **One authority.** Every millisecond↔bar conversion on the moving-heads path resolves
  through the `BeatGrid`'s detected boundaries.
- Renderer: `_bar_to_ms` returns `beat_grid.get_bar_start_ms(bar - 1)`, with a documented
  bounds fallback to the average for bars past the detected range (and past the end of
  the song).
- Planner: `_ms_to_bar` rounds to the **nearest detected downbeat**, taking the `BeatGrid`
  rather than a scalar tempo. The 120 BPM fallback survives only for the case where no
  grid is available at all, and that case is logged.
- `compile/transition_detector.py`'s duplicate average-grid formula routes through the
  same conversion.
- After this task the effects, the plan's bar numbers, and the "Twinklr Bars" timing track
  all refer to the same instants.

**Non-goals.** Do not change how the `BeatGrid` is *detected* (that is P2P-T8). Do not
change timing-track emission — Grid B is the correct one and stays. Do not repair the
display-side `_ms_to_planning_ref`/`resolve_start_ms` inverse-pair defect (P5-F1); the
display pipeline is deferred. Do not fix scheduler behavior (P1P-T5).

## Implementation approach

Files/symbols to touch:
- `packages/twinklr/core/sequencer/models/context.py` — `TemplateCompileContext._bar_to_ms`
  (and the docstring at `:113-115`, which currently describes the intended behavior and
  must become true rather than be deleted).
- `packages/twinklr/core/agents/sequencer/moving_heads/context.py` —
  `MovingHeadContext._ms_to_bar` (`:246`) and its call sites (`:194-195`); the parallel
  bar-count computation around `:153-164` uses the same nominal-tempo arithmetic and must
  be reconciled or routed through the same helper.
- `packages/twinklr/core/sequencer/timing/beat_grid.py` — `get_bar_start_ms`,
  `snap_to_nearest_bar` gain their first real callers; add bounds semantics if absent.
- `packages/twinklr/core/sequencer/moving_heads/compile/transition_detector.py` — the
  duplicated formula.
- Wiring: whatever supplies `MovingHeadContext` today with a scalar `tempo` must supply
  the `BeatGrid` instead. `agents/sequencer/moving_heads/stage.py` constructs the
  `BeatGrid` (`:136` at baseline) and the context, so the grid is available at that seam.

Design decisions already made (do not relitigate):
- The fix is **routing through the existing `BeatGrid` methods**, not writing new
  conversion math and not adding a fourth grid.
- `_ms_to_bar` **rounds to nearest**, not floors. Flooring is the defect.
- Out-of-range bars fall back to the average — a rendered section past the detected range
  must still produce effects, not raise.
- Cross-phase file ownership is accepted: this task edits phase-3-owned
  `agents/sequencer/moving_heads/context.py` as well as phase-4-owned renderer files.
  That is the point of bundling them.

Sequencing constraints (copied verbatim from `changes/twinklr-reactivation-review/build/plan/00-overview.md`):

> CF-2 grid fix spans agents-context (`_ms_to_bar`) and sequencer — one task, both halves
> (P1P-T4).

> `make validate` equivalents (check-only forms until P0-T4 lands the guard) must pass
> at every merge; golden tests (once P1P-T1 exists) must pass for any lane touching
> render/export code.

> **Verification currency**: evidence in specs is from baseline `aa8d325`. Executors
> must re-verify cited line numbers before editing (the tree will drift as phases land)
> — specs cite symbol + file, with line numbers as hints only.

From `changes/twinklr-reactivation-review/build/plan/02-phase-1p-render-truth.md`:

> **Lane R (render repair, serial — shared files in `sequencer/moving_heads/` +
> `curves/`)**: T3 → T4 → T5 → T6.

## Acceptance criteria

- [ ] `TemplateCompileContext._bar_to_ms` contains no `ms_per_bar` multiplication on the
      in-range path; it resolves through `beat_grid.get_bar_start_ms`.
- [ ] `MovingHeadContext._ms_to_bar` performs **nearest-downbeat** resolution against a
      `BeatGrid`; the `int(... ) + 1` floor is gone. Verifiable by grep for the floor
      expression.
- [ ] `get_bar_start_ms` and the nearest-bar resolution have real production callers
      (the review's "zero callers repo-wide" statement is no longer true).
- [ ] A test proves the three-way agreement directly: for the P1P-T2 fixture grid (whose
      `bar_boundaries[0] != 0` and whose spacing is non-uniform), the rendered start time
      of every section equals the "Twinklr Bars" marker for that section's start bar,
      **exactly** (0 ms tolerance for in-range bars).
- [ ] A test pins the round-trip: `_ms_to_bar(_bar_to_ms(b)) == b` for every bar in the
      detected range.
- [ ] A test pins the constant-offset case: with `bar_boundaries[0] = 1500 ms`, bar 1
      renders at 1500 ms, not 0 ms.
- [ ] Out-of-range bar numbers do not raise and fall back to the average, with a log line.
- [ ] `compile/transition_detector.py` uses the same conversion (grep shows no second
      `ms_per_bar`-based bar→ms formula on the moving-heads path).
- [ ] `make validate` check-only equivalents pass; golden suite regenerated with reviewed
      diffs.

**Golden-diff expectation (BEFORE/AFTER), 4-head reference rig, deterministic plan with
`bar_boundaries[0] != 0` and non-uniform spacing:**

```
BEFORE:
  Effect start/end times are multiples of the song-wide average ms_per_bar,
  anchored at 0 ms. The first effect starts at t=0 while the "Twinklr Bars"
  timing track's first marker sits at bar_boundaries[0] (non-zero).
  Later sections drift further from their markers as tempo deviates from the
  average.

AFTER:
  - EVERY effect start/end time in the golden moves. The first effect starts at
    bar_boundaries[0], matching the first "Twinklr Bars" marker exactly.
  - Per-section start times equal the corresponding bar-boundary values, not
    i × avg. A test asserts this equality, so the golden diff is a consequence,
    not the proof.
  - Timing-track content is UNCHANGED (Grid B was always right). A diff in the
    "Twinklr Bars"/"Twinklr Beats" markers is a FAIL — it means the task changed
    the wrong grid.
  - Effect PAYLOADS (Values= strings, E_SLIDER_DMX values) are unchanged except
    where a changed segment duration changes the sample spacing. Payload changes
    beyond that indicate scope creep into T3/T5 territory.
  - Section→bar assignment may change for sections whose detected start was
    previously floored down a whole bar; that reassignment is expected and must
    be visible in the diff as a section boundary moving LATER (toward its true
    position), never earlier.
```

## Tests

TDD: write the three-way agreement test first — it fails at baseline by exactly
`bar_boundaries[0]` plus drift.

| Test | Behavior pinned |
|---|---|
| `test_effect_start_matches_bars_timing_track` | The headline: effects and the "Twinklr Bars" track agree, on a non-uniform grid with a non-zero first downbeat |
| `test_bar_to_ms_uses_detected_boundaries` | `_bar_to_ms(1)` == `bar_boundaries[0]`, not 0 |
| `test_ms_to_bar_rounds_to_nearest_downbeat` | A section start 100 ms *after* a downbeat resolves to that bar; one 100 ms *before* the next downbeat resolves to the **next** bar (this is the assertion that fails on the floor implementation) |
| `test_bar_round_trip_is_identity` | `_ms_to_bar(_bar_to_ms(b)) == b` across the detected range |
| `test_out_of_range_bar_falls_back_to_average` | No raise past the end of the detected grid; documented fallback + log |
| `test_transition_boundaries_use_same_grid` | The duplicate formula is gone |
| `test_no_grid_available_falls_back_and_logs` | The 120 BPM path survives only as a logged last resort |
| Golden suite (P1P-T1) | Reviewed BEFORE/AFTER diff as specified above |

## Verification commands

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy .

uv run pytest tests/unit/timing -v
uv run pytest tests/unit/sequencer -v
uv run pytest tests/unit/agents/sequencer -v
uv run pytest tests/golden -v

# defect-specific greps the verifier runs
grep -rn "ms_per_bar" packages/twinklr/core/sequencer/moving_heads packages/twinklr/core/sequencer/models   # expect: only the documented out-of-range fallback
grep -n "int(beat_number / beats_per_bar) + 1" packages/twinklr/core/agents/sequencer/moving_heads/context.py  # expect: no match
grep -rn "get_bar_start_ms" packages/ | grep -v beat_grid.py    # expect: at least one production caller
```

No LOCAL-ONLY steps. No paid API calls.

## Effort & risk

**Effort: M.**

**Main risk: the planner-side change moves section boundaries, which changes which
template the planner would pick** — meaning a cached plan and a fresh plan may disagree
after this lands. Mitigation: the deterministic plan fixture is fixed input (no planner
run), so goldens isolate the renderer effect; and P1P-T9's prompt-content hashing +
deterministic session-ID work covers the cache-staleness hazard for real runs. If the
executor must invalidate a cache key to make behavior observable, note it in the handoff
rather than hand-bumping `cache_version` silently.

**Second risk: `get_bar_start_ms` has never run in production** (zero callers), so its
bounds behavior is unproven. Mitigation: test it directly — empty grid, single-bar grid,
bar index 0, bar index past the end — before wiring it in.

**Third risk: rounding to nearest can collapse two short sections onto the same bar.**
Mitigation: assert monotonic non-decreasing section starts after conversion, and if a
collapse occurs, preserve ordering rather than silently overlapping; record the case for
P1P-T5, which owns short-section rendering.
