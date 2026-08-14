# P3-T1 — Composition timing repair

Phase: 3 (Show Convergence / M3) · Lane: C (composition repair) · Executor: opus ·
Verifier: opus · Depends on: P2P-T8 (real grid)

## Objective

The display composition engine must place effects where its own expansion math says
they go. Today every coordination-mode placement round-trips exact milliseconds
through an integer bar/beat reference and a 5-bucket duration category, and the
reverse conversion is not the inverse of the forward one — so placements shift by up
to a full beat on perfectly steady-tempo material, sub-beat ripple offsets collapse,
and computed slot durations are re-quantized to 1/4/12/24 beats. `SEQUENCED` on top
of that lights every group continuously instead of one at a time. After this task,
window expansion is millisecond-native end to end, `SEQUENCED` produces
non-overlapping round-robin slots, TRIM overlap resolution stops leaving dark gaps it
did not need to create, and per-run composition state does not leak between
`compose()` calls.

## Evidence & background

Findings: **P5-F1** (HIGH), **P5-F2** (HIGH), **P5-F12** (MEDIUM, mechanism corrected
at verification), **P5-M2** (MEDIUM, latent), **P5-M6** (implementation constraint).
Consolidated as **SF-6** in `reviews/findings.md`. Detail:
`changes/twinklr-reactivation-review/reviews/phases/display-rendering-and-xlights-io.md`
§10. Verifier corrections that supersede the first-draft text:
`changes/twinklr-reactivation-review/reviews/verification.md` §"Phase 5".

> **The phase plan flags this explicitly**: "T1/T2 mechanics MUST be copied from the
> corrected verifier versions in `verification.md` (both had inverted mechanisms in
> the original phase doc)." The corrected mechanics are quoted below. Implement
> against these, not against any other reading of the bug.

Line numbers are hints from baseline `aa8d325`; all citations below were re-verified
against the tree while authoring this spec, but re-verify before editing.

### F1 — the round trip is not a round trip (verifier-sharpened form)

From `verification.md` §"Phase 5":

> F1 sharpened: `_ms_to_planning_ref` is not the inverse of `resolve_start_ms` at all
> — constant offset of `beat_boundaries[0]` plus drift, then floored (every placement
> can shift a full beat).

And from the phase doc's F1 (verifier addition, the sharpest form):

> The forward function measures from ms=0 using a constant beat length; the reverse
> indexes into `beat_boundaries`, whose origin is `beat_boundaries[0]` — the first
> detected beat, which is generally **not** 0. The two therefore differ by a constant
> offset before any tempo drift is considered, and the result is then floored. **Every
> expanded placement can shift by a full beat**, uniformly across the song, on
> perfectly steady-tempo material. This is not a rounding artifact; the round trip is
> simply not a round trip.

Verified code, `sequencer/display/composition/engine.py`:

- `_ms_to_planning_ref` (`:688-707`) — forward direction, constant beat length from
  nominal tempo, then floored:
  ```python
  ms_per_beat = 60_000.0 / self._beat_grid.tempo_bpm
  beats_per_bar = self._beat_grid.beats_per_bar
  total_beats = ms / ms_per_beat
  bar_0 = int(total_beats // beats_per_bar)
  beat_in_bar = int(total_beats % beats_per_bar)
  ```
- `_ms_to_duration` (`:709-741`) — buckets to HIT (≤3 beats) / BURST (≤6) / PHRASE
  (≤16) / EXTENDED (≤32) / SECTION.
- `_resolve_step_ms` (`:665-686`) and both converters use the same constant
  `60_000.0 / tempo_bpm`, never `beat_boundaries`.

Reverse direction, `sequencer/display/composition/timing_resolver.py`:

- `resolve_start_ms` (`:52-65`) indexes the grid:
  `absolute_beat = (song_bar_0 * beats_per_bar) + beat_within_bar`, clamped, then
  `ms = self._beat_grid.get_beat_time_ms(absolute_beat)` → `_snap_to_grid(ms)` (20 ms).
  `BeatGrid.get_beat_time_ms` (`sequencer/timing/beat_grid.py:235-250`) is literally
  `return self.beat_boundaries[beat_index]`, so the origin is `beat_boundaries[0]`.
- `resolve_end_ms` (`:67-123`) re-expands the category via `_resolve_beat_count`
  (`:125-148`) with `duration_bias=0.5`, against `DURATION_BEATS`
  (`sequencer/vocabulary/duration.py:34-40`) — a computed 3-beat SEQUENCED slot
  becomes a 1-beat HIT; a 5-beat slot becomes 4.

Three call sites feed the round trip: `_expand_sequenced` (`:507-508`),
`_expand_ripple` (`:580-581`), `_expand_call_response` (`:636-637`).

Concrete F1 consequence quoted from the phase doc: "A RIPPLE with `phase_offset=0.5`
on 1-beat steps produces group starts at 0.0, 0.5, 1.0, 1.5 beats → floors to beats
0, 0, 1, 1 → groups collapse into pairs and the ripple becomes a two-step unison."

### F2 — SEQUENCED does not sequence (one-line fix, verifier-confirmed)

`_expand_sequenced` (`engine.py:479-531`) documents "non-overlapping round-robin
slots, one group at a time" (`:487-491`). Verified code:

```python
group_offset_ms = group_idx * step_ms
current_ms = window_start_ms + group_offset_ms      # :496-497
...
slot_duration_ms = step_ms * group_count            # :501  ← the bug
slot_end_ms = min(current_ms + slot_duration_ms, window_end_ms)
...
current_ms += slot_duration_ms                      # :522
```

Each group's slots are therefore **contiguous** and every group is lit continuously
from its staggered start to the window end. "With 3 groups and a 2-beat step, all
three groups are simultaneously active from beat 4 onward. The only sequencing
visible to a viewer is the first stagger."

Fix, quoted verbatim from the phase doc (verifier: "re-derived; one-line fix
confirmed"): **slot *i* of group *g* = `[start + (i*N + g)*step, +step)`** — i.e. the
emitted duration is `step_ms`, not `step_ms * group_count`; the advance stays
`step_ms * group_count`.

### F12 — TRIM deletes coverage it did not need to delete (mechanism corrected)

From the phase doc, with the verifier's correction applied in place:

> _Mechanism corrected on verification: the harm does not come from trimming against
> neighbours that are later dropped as eclipsed, but from trimming against **short
> neighbours that survive**._
>
> Given A=[0,100), B=[10,20), C=[50,200) sorted by start: A is trimmed to end at B's
> start (10), B survives untouched as [10,20), and C is kept as [50,200). The interval
> 20–50 ms is now dark — A was trimmed to make room for a 10 ms neighbour and never
> restored for the gap that neighbour left behind. A long base event nested around a
> short accent loses its entire tail to a 10 ms interruption. The eclipse branch
> (`:1014-1016`) is a separate and comparatively benign case.

Verified code: `_resolve_overlaps` (`engine.py:975-1020`) trims `event` against
`events[i + 1]` taken from the **original** sorted list, never against the running
`resolved` list, and never re-extends. Also flagged in the same finding: "the 'later
event wins' policy is applied without regard to lane or intensity, so a WHISPER accent
can truncate a PEAK base event."

### M2 — `_layer_blend_modes` is never reset between `compose()` calls

`self._layer_blend_modes` is initialized once in `__init__` (`engine.py:173`) and
never cleared in `compose()` (`:179-224`); it accumulates through first-wins guards at
`:263-264`, `:361-362`, and `:385-386`. A second `compose()` on the same engine
inherits every blend-mode decision from the first run, and the **stale** values win.
Latent today because `DisplayRenderer.render` constructs a fresh engine per call
(`renderer.py:178-187`) — "a trap for exactly the two things this subsystem needs next
— batch rendering and A/B comparison runs."

### M6 — the constraint on the F1 fix (carried forward deliberately)

> the `section_start_bar=0` fallback (`engine.py:250-252`) and the section-relative
> expansion convention (`engine.py:416-418`) are **intentional**. An ms-native rewrite
> of window expansion that does not preserve them will double-apply or drop the
> section offset in `_compose_placement_compiled` and break placements that currently
> resolve correctly. Any P5-F1 fix must ship with a test that pins section-offset
> behavior for both the mapped and unmapped cases.

Verified: `_compose_section` (`:246-252`) sets `section_start_bar` from the section
bar map when present and `0` otherwise; `_expand_window` (`:416-420`) resolves window
bounds with `resolve_start_ms(window.start)` **without** `section_start_bar` — i.e.
expansion works in section-relative time — and `_compose_placement_compiled`
(`:783-786`) re-applies the section offset via
`resolve_start_ms(placement.start, section_start_bar=section_start_bar)`.

## Current behavior

1. `_expand_window` resolves the window to section-relative ms, dispatches to one of
   three expanders, each of which computes exact ms schedules and then discards them
   by converting to `(PlanningTimeRef, EffectDuration)`.
2. `_compose_placement_compiled` converts those categories back to ms through the
   BeatGrid — a different origin and a different beat-length source than the forward
   conversion used — then snaps to a 20 ms grid.
3. `SEQUENCED` emits `step_ms * group_count`-long slots at `step_ms`-staggered starts,
   so groups overlap for the whole window.
4. Overlap resolution trims each event against its original-list successor and never
   re-extends, so a short surviving neighbour permanently deletes the remainder of a
   long event.
5. `_layer_blend_modes` persists across `compose()` calls on one engine instance.

## Target behavior

1. **Ms-native expansion.** `_expand_sequenced`, `_expand_ripple`, and
   `_expand_call_response` return placements carrying **absolute section-relative
   millisecond start/end**, and `_compose_placement_compiled` gains an ms-native path
   that consumes them without any bar/beat or duration-bucket round trip. The
   categorical path (`PlanningTimeRef` + `EffectDuration` → `TimingResolver`) remains
   the path for **planner-authored** placements and is otherwise unchanged.
2. **Section offset preserved.** For expanded placements the section offset is applied
   exactly once. When the section bar map is present, expansion output lands at
   `section_start_ms + relative_ms`; when it is absent (`section_start_bar = 0`
   fallback), it lands at the same ms the current code intends for that convention.
   Neither double-applies nor drops the offset.
3. **BeatGrid remains the sole timing authority.** Any beat-length arithmetic that
   survives in expansion (e.g. `_resolve_step_ms`) reads the BeatGrid's boundaries
   rather than the constant `60000 / tempo_bpm`, so tempo drift no longer splits the
   two conversions. The 20 ms snap stays where it is today (in `TimingResolver`), and
   ms-native placements are snapped through the same helper so grid behavior is
   identical for both paths.
4. **SEQUENCED sequences.** Slot *i* of group *g* spans
   `[window_start + (i*N + g)*step_ms, +step_ms)` clipped to `window_end`, where
   `N = len(group_order)`. At any instant at most one group is active from a given
   SEQUENCED window.
5. **TRIM leaves no unnecessary gaps.** Overlap resolution operates against the
   running resolved list and re-extends (or splits) a trimmed event to cover the
   interval after a short neighbour ends, up to its original end or the next real
   conflict.
6. **State resets.** `compose()` clears `_layer_blend_modes` (and any other
   per-run accumulator on the engine) at entry, so repeated `compose()` calls on one
   instance are order-independent and identical to fresh-instance runs.

**Non-goals** (do not do these here):

- Do **not** touch lane blend-mode key allocation or the recipe-vs-lane precedence
  question — that is P3-T2 (P5-F3), the next task in this lane.
- Do **not** change `DURATION_BEATS` or anything under `sequencer/vocabulary/`. The
  phase review notes phase 4 owns that contract and any change must be coordinated;
  this task removes the *dependency* of expanded placements on the buckets, it does
  not redefine them.
- Do **not** change the 20 ms snap value or introduce a configurable grid (modernization
  M6 interacts here; the phase doc requires the two be sequenced together, and this
  task deliberately holds the grid constant).
- Do **not** re-architect `RecipeCompiler`/`TemplateCompiler`, effect-type validation,
  or the writer.

## Implementation approach

Files expected to change:

- `packages/twinklr/core/sequencer/display/composition/engine.py` — expanders,
  `_compose_placement_compiled`, `_resolve_overlaps`, `compose()` state reset,
  `_resolve_step_ms`.
- `packages/twinklr/core/sequencer/display/composition/models.py` (or wherever
  `GroupPlacement` lives — re-verify) — carry absolute ms on expanded placements.
- `packages/twinklr/core/sequencer/display/composition/timing_resolver.py` — expose an
  ms-native entry (snap + clamp) so both paths share one grid policy.

Design decisions already made — do not relitigate:

- **Keep milliseconds, do not fix the converters.** The phase review's §7 comparison
  states the chosen remedy directly: "Coordination expansion → keep milliseconds. The
  expansion functions already compute exact ms. Having them return `(start_ms,
  end_ms)` placements directly, with the categorical path used only for
  planner-authored placements, removes P5-F1 entirely and is a smaller change than any
  alternative."
- `_ms_to_planning_ref` / `_ms_to_duration` become unused by the expanders. Delete
  them only if grep confirms no remaining production caller; otherwise leave them and
  say so in the PR body. Do not "fix" them into a true inverse — that is the rejected
  alternative.
- The SEQUENCED correction is the exact formula above. Do not redesign the mode.
- TRIM stays a trim-based policy (no rewrite to an interval tree); the fix is
  running-list resolution plus re-extension/split.

Sequencing constraints copied verbatim from `changes/twinklr-reactivation-review/build/plan/00-overview.md`:

> **Verification currency**: evidence in specs is from baseline `aa8d325`. Executors
> must re-verify cited line numbers before editing (the tree will drift as phases
> land) — specs cite symbol + file, with line numbers as hints only.

> `make validate` equivalents (check-only forms until P0-T4 lands the guard) must pass
> at every merge; golden tests (once P1P-T1 exists) must pass for any lane touching
> render/export code.

> A lane's tasks land as one PR-style merge per task (small, reviewable diffs).

> Nothing in this program authorizes pushes/PRs to remotes or paid API calls beyond
> each spec's stated test budget; live-LLM and xLights-GUI tests are marked
> `LOCAL-ONLY` in specs and excluded from CI.

From `changes/twinklr-reactivation-review/build/plan/06-phase-3-show-convergence.md`: Lane C is `T1 → T2`; T1 is the
first task in the lane and P3-T2 rebases on it.

Dependency note: this task depends on **P2P-T8** (MIR adoption) only for the *source*
of the BeatGrid — the grid interface is unchanged. If P2P-T8's A/B gate kept the
existing DSP, this task is unaffected: it consumes `BeatGrid.beat_boundaries` either
way.

## Acceptance criteria

Composition-level (assertable without xLights):

1. For a BeatGrid whose `beat_boundaries[0] != 0` and constant tempo, an expanded
   SEQUENCED/RIPPLE/CALL_RESPONSE placement's rendered `start_ms` equals the ms the
   expander computed (within the 20 ms snap), **not** offset by `beat_boundaries[0]`
   and not floored to a beat.
2. For a BeatGrid with tempo drift (non-uniform `beat_boundaries`), expanded placement
   times track the boundaries, not `60000 / tempo_bpm`.
3. RIPPLE with `phase_offset=0.5` on a 1-beat step produces **distinct** start times
   for consecutive groups (0.0/0.5/1.0/1.5 beats), not the collapsed 0/0/1/1 pairs.
4. A computed 3-beat SEQUENCED slot renders as ~3 beats, not 1 (HIT); a 5-beat slot
   renders as ~5, not 4.
5. SEQUENCED with N groups over a window: for every pair of events emitted from that
   window, the intervals are disjoint; group order cycles `g0, g1, …, gN-1, g0, …`;
   each slot is `step_ms` long (final slot clipped to the window end).
6. TRIM: for input events A=[0,100), B=[10,20), C=[50,200) on one layer, the resolved
   output covers [0,10) ∪ [10,20) ∪ [20,50) ∪ [50,200) with no dark interval at
   20–50 ms. (Whether A is re-extended or split is an implementation choice; the
   coverage assertion is the criterion.)
7. Section offset: with a section bar map present, and again with it absent
   (`section_start_bar = 0`), expanded placements land at the same absolute ms the
   current code intends for that convention — pinned by the M6-mandated test in both
   cases.
8. `compose()` called twice on one `CompositionEngine` with two different plan sets
   yields byte-identical `RenderPlan` output (modulo `render_id`) to two
   fresh-instance runs.
9. Planner-authored (non-expanded) placements are unchanged: their timing still flows
   through `TimingResolver.resolve_start_ms` / `resolve_end_ms` with the same results
   as before this task.

Golden-diff expectations (run through the P1P-T1 harness for any display golden
fixtures that exist by merge time; if none exist yet, record the RenderPlan-level
snapshot as the diff artifact instead):

- BEFORE: SEQUENCED windows show all groups' effects overlapping from the Nth step to
  window end; RIPPLE groups share duplicate start times; expanded effect starts sit on
  beat boundaries offset by a constant from the expander's own arithmetic.
- AFTER: SEQUENCED effects are disjoint and round-robin; RIPPLE starts are distinct
  and sub-beat; expanded starts match the expander's ms (± the 20 ms snap); MH golden
  outputs are **byte-identical** to BEFORE (this task touches no moving-heads code).

## Tests

TDD — write these failing first, in
`tests/unit/sequencer/display/composition/`:

1. `test_expansion_ms_native.py::test_sequenced_start_matches_expander_ms` — BeatGrid
   with `beat_boundaries[0] = 137.0` (non-zero origin), constant tempo; assert
   resolved start ms for each SEQUENCED slot equals the expander's computed ms within
   the snap tolerance. Pins F1's constant-offset half.
2. `…::test_expansion_tracks_drifting_beat_grid` — non-uniform boundaries; assert
   placements follow boundaries, not nominal tempo. Pins F1's drift half.
3. `…::test_ripple_sub_beat_offsets_survive` — `phase_offset=0.5`, 1-beat step, 4
   groups; assert 4 distinct start times. Pins F1's floor half.
4. `…::test_slot_duration_not_rebucketed` — 3-beat and 5-beat computed slots; assert
   rendered durations ≈ 3 and 5 beats. Pins F1's duration-bucket half.
5. `test_sequenced.py::test_sequenced_slots_are_disjoint` and
   `…::test_sequenced_round_robin_order` — pins F2. **Note**: `test_sequenced.py`
   exists today and cannot run in a fresh checkout (P5-F11: it builds a
   `RecipeCompiler` from `TemplateStore.from_directory(repo/data/templates)`, which is
   gitignored and absent, at `:63-72`). This task's new tests **must not** depend on
   `data/templates` — construct the engine with an in-test template/recipe fixture. If
   P1K-T3's tracked catalog has landed by merge time, prefer that; either way the new
   tests must pass from a clean clone.
6. `test_overlap_resolution.py::test_short_neighbour_does_not_delete_tail` — the
   A/B/C case above. Pins F12.
7. `test_overlap_resolution.py::test_full_eclipse_still_drops` — the benign eclipse
   branch keeps its current behavior (regression guard).
8. `test_engine_state.py::test_compose_resets_layer_blend_modes` — two `compose()`
   calls on one engine with conflicting blend modes; assert the second run's blend
   modes come from the second plan. Pins M2.
9. `test_section_offset.py::test_section_offset_applied_once_mapped` and
   `…::test_section_offset_applied_once_unmapped` — the M6-mandated pair. Required;
   the task is not done without both.

Existing tests that must keep passing (or be updated with a written justification in
the PR body, not silently): everything under
`tests/unit/sequencer/display/composition/` and
`tests/unit/sequencer/display/test_renderer_overlay.py`. Tests that fail **only**
because of the absent `data/templates` are pre-existing (P5-F11: 52 such failures at
baseline) and are not this task's to fix — but do not add to that count.

## Verification commands

```bash
# check-only gates (no mutation)
uv run ruff format --check .
uv run ruff check .
uv run mypy .

# targeted
uv run pytest tests/unit/sequencer/display/composition/ -v
uv run pytest tests/unit/sequencer/display/ -v

# full suite — compare failure count and identity against the baseline record in
# reviews/verification.md §"Stage 4 runtime baseline" (120 failed / 4040 passed).
# No NEW failures are permitted; the 52 data/templates failures are pre-existing.
uv run pytest tests/ -q

# render/export golden gate (required by the overview for any lane touching
# render/export code) — exact invocation per P1P-T1's harness
uv run pytest tests/golden -v
```

LOCAL-ONLY: none. This task needs no xLights GUI and no API calls. **Test budget: $0
— this task must make zero paid API calls.**

## Effort & risk

**Size: M** (the phase review estimated ~1 day for F1, ~1 hour for F2, ~2 hours for
F12, ~15 minutes for M2, plus tests).

**Main risk: the section-offset convention.** An ms-native expansion path that
forgets `section_start_bar=0`/section-relative expansion will double-apply or drop the
offset and break placements that currently resolve correctly — the review calls this
out as a named constraint (P5-M6) precisely because it is the easy mistake here.
*Mitigation*: write the two section-offset tests (Tests #9) **first**, before touching
the expanders, and keep them green through every intermediate commit.

**Secondary risk: no runnable coverage of the code being changed.** The existing
coordination-mode tests cannot run in a clean checkout (P5-F11), which is the
proximate reason these defects survived. *Mitigation*: every new test in this task is
required to be corpus-independent, so the repair arrives with coverage that actually
executes in CI.

## Backlog addition (P1P-T4 verification, 2026-08-13)
display/composition/section_map.py keeps the last private nearest-bar
implementation (_find_nearest_bar_index) — route it through
BeatGrid.nearest_bar_index as part of this task's grid unification.
