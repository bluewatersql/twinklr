# P3-T2 — Blend modes + effect fallback truth

Phase: 3 (Show Convergence / M3) · Lane: C (composition repair) · Executor: opus ·
Verifier: opus · Depends on: P3-T1

## Objective

Two planner inputs currently vanish inside the display renderer without a trace. A
lane's `blend_mode` is recorded against one layer-index space and consumed from
another, so it is **structurally incapable** of reaching RHYTHM or ACCENT output at
all. And an `effect_type` the handler registry does not recognize silently falls back
to the flat `On` handler, emitting a valid `.xsq` full of correctly-timed,
correctly-coloured, visually-wrong blocks with no artifact anywhere that says so.
After this task, lane blend modes either reach every emitted layer or are deliberately
and visibly not used; and an unrecognized effect type is rejected at recipe admission,
with any surviving fallback surfaced into `WriteResult.warnings` and the trace
sidecar.

## Evidence & background

Findings: **P5-F3** (MEDIUM — HIGH in the first draft; **mechanism inverted at
verification**), **P5-F8 + P5-M1** (MED-HIGH, merged at verification). Related:
P5-M2 (fixed in P3-T1), P5-F7 (parameter validation — adjacent, not in scope here).
Consolidated as SF-6 and CC-3 in `reviews/findings.md`. Detail:
`.../reviews/phases/display-rendering-and-xlights-io.md` §10; corrections in
`.../reviews/verification.md` §"Phase 5".

> **The phase plan flags this explicitly**: "T1/T2 mechanics MUST be copied from the
> corrected verifier versions in `verification.md` (both had inverted mechanisms in
> the original phase doc)." Implement against the corrected mechanics below.

### F3 — the corrected mechanism (structural loss, not contamination)

From `verification.md` §"Phase 5":

> **F3 HIGH→MEDIUM, mechanism inverted**: in normal ordering the recipe wins and
> RHYTHM/ACCENT lane blend modes are silently DISCARDED (not emitted on BASE layers);
> restated as "`lane_plan.blend_mode` is structurally incapable of reaching
> RHYTHM/ACCENT output" (allocator keys 0/2/4 vs lanes emitting on 6-16). Fix
> unchanged.

From the phase doc, with the verifier's correction applied in place:

> _Mechanism corrected by the verifier; the first draft had the direction of the
> collision backwards. The defect is real but its effect is **silent discard**, not
> contamination._
>
> The two index spaces do not merely collide — **they barely intersect**. Lane blend
> modes are only ever written to keys 0, 2, and 4, all of which lie inside the BASE
> lane's block. RHYTHM emits on 6–11 and ACCENT on 12–17, where no lane blend mode is
> ever registered. So:
>
> - **`lane_plan.blend_mode` can never reach RHYTHM or ACCENT output at all.** Those
>   layers take their blend mode from the recipe (`ce.layer_blend_mode`), and the
>   planner's lane-level choice is silently dropped. This is the finding.
> - Within the BASE block, ordering decides who wins. `_compose_section` registers key
>   0 before composing that lane's coordination plans, so BASE/BACKGROUND takes the
>   lane value and its recipe blend mode is discarded. Keys 2 and 4 are normally
>   claimed *first* by BASE's own FOREGROUND/TEXTURE recipes during that same
>   iteration, so when the RHYTHM and ACCENT iterations later try to register there,
>   the `if blend_key not in self._layer_blend_modes` guard (`engine.py:361-362`)
>   rejects them — **the recipe wins and the lane value is discarded**, which is the
>   opposite of what the first draft claimed.
> - Residual, conditional: if a BASE lane emits nothing at FOREGROUND/TEXTURE depth in
>   an early section, keys 2/4 stay free and a later lane's value can occupy them, so a
>   subsequent section's BASE/FOREGROUND events would inherit a RHYTHM blend mode. This
>   cross-section contamination is possible but not the normal path.

Verified code:

- `engine.py:256-264` — `layer_idx = self._layer_allocator.allocate(lane)` (the legacy
  simple allocator), then `self._layer_blend_modes[(element_name, layer_idx)] =
  blend_mode` under a first-wins `if key not in` guard.
- `sequencer/display/composition/layer_allocator.py:47-52` — `_COMPAT_LAYER_MAP =
  {BASE: 0, RHYTHM: 2, ACCENT: 4}` (the keys lane blend modes are written to).
- `layer_allocator.py:20-38` — the space events are actually placed in:
  `_LANE_BLOCK_SIZE = 6`, `_DEFAULT_LANE_BASE = {BASE: 0, RHYTHM: 6, ACCENT: 12}`
  (comments say layers 0-5 / 6-11 / 12-17), `_DEPTH_OFFSET = {BACKGROUND: 0,
  MIDGROUND: 1, FOREGROUND: 2, ACCENT: 3, TEXTURE: 4}`.
- `engine.py:359-362` — placement uses `allocate_sub_layer(lane, ce.visual_depth)` and
  registers `ce.layer_blend_mode` under the same first-wins guard.
- `engine.py:1072` — consumption: `blend_mode = self._layer_blend_modes.get(blend_key,
  "Normal")`.
- `LayerAllocator.resolve_blend_mode` maps `GPBlendMode` → xLights
  `T_CHOICE_LayerMethod` via `_BLEND_MODE_MAP` (`layer_allocator.py:40-45`).

Fix, quoted from the phase doc (unchanged by verification):

> **Fix (unchanged):** delete the `_compose_section` blend-tracking loop (the sub-layer
> path at `:358-362` already covers every emitted layer) or key it by
> `allocate_sub_layer`. Then decide deliberately whether `lane_plan.blend_mode` should
> override recipe blend modes — today the question has never been answered, only
> avoided. ~1 hour.

### F8 + M1 — unrecognized effect types render silently as flat `On`

From the phase doc (P5-M1 is verifier-added and merged into F8, raising it to
MED-HIGH):

> **P5-M1 (verifier-added, merged here): an unrecognized effect type renders silently
> as a flat `On`.** `HandlerRegistry.dispatch` (`display/effects/registry.py:93-108`)
> looks up `event.effect_type`; on a miss it falls back to the default handler — set
> to the `On` handler at `handlers/__init__.py:94` — emitting only a
> `logger.warning`. That warning goes to the log and **nowhere else**: it is not added
> to `EffectSettings.warnings`, so it never reaches `WriteResult.warnings`
> (`writer.py:226`), never reaches `RenderResult.warnings`, and never reaches the
> trace sidecar. `RenderEvent.effect_type` is a plain `str`
> (`models/render_event.py`) populated from recipe JSON or, on the placeholder path,
> from `resolve_effect_type` — neither validated against `registry.registered_types`.
>
> This is the concrete answer to "what does wrong output actually look like here": a
> recipe naming an effect Twinklr does not implement (a typo, an xLights effect with
> no handler, an LLM-invented name) produces a **valid `.xsq` full of flat `On`
> blocks** — correctly timed, correctly colored, visually wrong, and with no artifact
> anywhere in the output that says so.
>
> **Fix:** validate `effect_type` against the registry at compile time and fail
> loudly, or at minimum propagate the fallback into `EffectSettings.warnings` and the
> trace sidecar. ~2 hours, and it is the highest-value observability fix in the phase.

Verified code: `sequencer/display/effects/registry.py:95-108` —
`handler = self._handlers.get(event.effect_type)`; on `None` with a default set it
logs `"No handler for effect type '%s', using default '%s'"` and dispatches to the
default; `registered_types` is exposed as a property. `handlers/__init__.py:93-94` —
`# On is the fallback for unknown effect types` / `registry.set_default(on_handler)`.
`export/writer.py:226` — `result.warnings.extend(settings.warnings)`; trace entries at
`:258, :267-292`.

Related F8 half (not the primary target here, but do not regress it): the recipe path
sets `base_params = {}` when the recipe supplies a real effect type
(`recipe_compiler.py:144-146`), so recipe params whose keys don't match a handler's
`.get()` name are dropped silently, and `effect_map.resolve_effect_type` is the live
resolver (`recipe_compiler.py:141`).

## Current behavior

- Lane blend modes are written to `(element, 0|2|4)` and read from `(element,
  sub_layer)` where sub-layers are 0–4 (BASE), 6–10 (RHYTHM), 12–16 (ACCENT) plus
  overlays. RHYTHM/ACCENT reads never find a lane value; BASE reads find one only at
  key 0, and keys 2/4 are normally claimed by BASE's own recipes first.
- The consumption default is `"Normal"` (`engine.py:1072`), so a dropped lane choice
  is indistinguishable from an explicit Normal.
- An unregistered `effect_type` silently becomes `On`. The only signal is a log line.
  `WriteResult.warnings`, `RenderResult.warnings`, and the trace sidecar all stay
  clean.

## Target behavior

**Blend modes**

1. Exactly one index space carries blend modes: the one events are actually placed in
   (`allocate_sub_layer`). The `_compose_section` blend-tracking loop over
   `allocate(lane)` is either deleted or re-keyed by `allocate_sub_layer` — no
   `_COMPAT_LAYER_MAP` key is written to `_layer_blend_modes` any more.
2. The precedence question is **answered explicitly in code and in a decision note**,
   not left to first-wins ordering. Decide and implement one of:
   - *lane wins*: `lane_plan.blend_mode` overrides `ce.layer_blend_mode` for every
     layer in that lane; or
   - *recipe wins, lane is the default*: the recipe value is used when the recipe sets
     one, and the lane value fills in otherwise.
   Whichever is chosen, it must be uniform across BASE/RHYTHM/ACCENT (no
   depth-dependent or ordering-dependent behavior) and stated in the module docstring
   plus a durable note (see "Implementation approach").
3. A lane blend mode that cannot be honoured (for any reason that survives the fix)
   produces a `CompositionDiagnostic`, not silence.
4. Cross-section contamination (the F3 residual) is impossible: the map's keys are the
   same space as its reads, and P3-T1 already resets the map per `compose()`.

**Effect fallback**

5. `effect_type` is validated against `HandlerRegistry.registered_types` **at recipe
   admission** — i.e. at the point where a recipe/compiled effect first names an
   effect type, before composition builds a `RenderEvent` — and an unrecognized type
   fails loudly with a message naming the offending type, the recipe/template id, and
   the closest registered types.
6. If any fallback path survives (e.g. a deliberately lenient mode, or the
   placeholder/`resolve_effect_type` path), the fallback is recorded in
   `EffectSettings.warnings` so it flows into `WriteResult.warnings` →
   `RenderResult.warnings`, **and** is marked on the trace sidecar entry for the
   affected effect. "Logged only" is not acceptable for any surviving path.
7. `RenderResult`/`WriteResult` expose a non-zero count of fallback substitutions, so
   a caller (and P3-T8's evaluation) can assert "zero silent substitutions".

**Non-goals**

- Do not implement per-parameter range validation or settings-string escaping (P5-F6 /
  P5-F7) — adjacent, separately scoped.
- Do not do the handler-table refactor (24 handlers → data table). Tempting here;
  it is not this task.
- Do not wire `resolved_color` / `timing_offset_beats` / layer `mix` (the other half of
  P5-F8's computed-and-discarded list). Out of scope; record them as still-open in the
  PR body so P3-T5/T8 can see them.
- Do not touch the moving-heads path.

## Implementation approach

Files expected to change:

- `packages/twinklr/core/sequencer/display/composition/engine.py` — remove/re-key the
  `_compose_section` blend loop; diagnostics.
- `packages/twinklr/core/sequencer/display/composition/layer_allocator.py` — if
  `_COMPAT_LAYER_MAP`/`allocate` loses its last production caller, mark it dead and
  delete it (grep first; the review's dead-code standard is "delete when grep confirms
  zero production callers").
- `packages/twinklr/core/sequencer/display/composition/recipe_compiler.py` and/or
  `template_compiler.py` — admission-time effect-type validation.
- `packages/twinklr/core/sequencer/display/effects/registry.py` — expose the fallback
  as structured data rather than only a log line.
- `packages/twinklr/core/sequencer/display/export/writer.py` — thread the fallback
  warning into `WriteResult.warnings` and the trace entry.
- `packages/twinklr/core/sequencer/display/renderer.py` — surface counts on
  `RenderResult`.

Design decisions already made — do not relitigate:

- The blend-mode index space is `allocate_sub_layer`'s. The compat space is legacy.
- Validation happens **at admission**, with warning propagation as the belt-and-braces
  second half — the phase doc offers "or at minimum propagate"; this spec requires
  **both**, because the phase's central critique is that display failures are
  "plausible output, no signal".
- The trace sidecar is named in the review as "the best observability artifact in the
  phase" and "the only quality-evidence mechanism"; extending it is the intended
  direction, not a new invention.

The precedence decision (target behavior #2) is design-bearing but **owner-visible only
through this task's PR**: record it in
`memories/decisions/` (new decision record, per `AGENTS.md` knowledge placement) with
the rationale and the alternative rejected. Do not put it only in a code comment.

Sequencing constraints copied verbatim from `changes/twinklr-reactivation-review/build/plan/00-overview.md`:

> **Verification currency**: evidence in specs is from baseline `aa8d325`. Executors
> must re-verify cited line numbers before editing (the tree will drift as phases
> land) — specs cite symbol + file, with line numbers as hints only.

> `make validate` equivalents (check-only forms until P0-T4 lands the guard) must pass
> at every merge; golden tests (once P1P-T1 exists) must pass for any lane touching
> render/export code.

> Cross-lane file conflicts are called out in the task tables; when unavoidable, the
> later lane rebases.

From `changes/twinklr-reactivation-review/build/plan/06-phase-3-show-convergence.md`: Lane C is `T1 → T2`; **Lane X (T6,
unified export core) runs after T2** and touches `writer.py` as well — T6 rebases on
this task, so keep the writer changes here minimal and additive.

## Acceptance criteria

1. Grep shows zero writes into `_layer_blend_modes` keyed by `LayerAllocator.allocate`
   / `_COMPAT_LAYER_MAP` results.
2. A plan with `lane_plan.blend_mode` set on a RHYTHM lane produces RHYTHM-layer
   effects whose emitted `T_CHOICE_LayerMethod` reflects the chosen precedence rule —
   demonstrably **not** the unconditional `"Normal"` default of today.
3. The same assertion holds for ACCENT.
4. Precedence is uniform: a fixture exercising BASE/BACKGROUND, BASE/FOREGROUND,
   RHYTHM, and ACCENT in one section yields blend modes explainable by one stated rule,
   with no dependence on lane iteration order.
5. Composing two sections where the first emits nothing at BASE/FOREGROUND cannot make
   the second section's BASE/FOREGROUND inherit a RHYTHM blend mode (the F3 residual).
6. A recipe naming an unregistered `effect_type` fails at admission with an error
   naming the type and the source recipe/template — it does **not** produce a
   `RenderPlan`.
7. If a fallback path is deliberately retained, exercising it yields: a non-empty
   `WriteResult.warnings` entry naming the substituted type, the same information on
   the affected trace-sidecar entry, and a non-zero substitution count on
   `RenderResult`.
8. `registry.dispatch`'s log line still fires (it is not a regression to keep it), but
   no test relies on logs as the only signal.

Golden-diff expectations (through the P1P-T1 harness; RenderPlan/`.xsq`-text snapshot
if no display golden exists yet):

- BEFORE: every RHYTHM/ACCENT layer carries `T_CHOICE_LayerMethod=Normal` regardless of
  the plan; an unknown-effect fixture emits `On` blocks with an empty warnings list.
- AFTER: RHYTHM/ACCENT layers carry the planned/recipe method per the stated rule; the
  unknown-effect fixture fails admission (or, on the retained-fallback path, emits with
  a populated warnings list and a marked trace entry).
- Moving-heads golden outputs: **byte-identical** to BEFORE (this task touches no MH
  code).

## Tests

TDD — failing first. All new tests must run from a clean clone (no dependency on the
gitignored `data/templates`; see P5-F11 — 52 baseline failures trace to it).

In `tests/unit/sequencer/display/composition/`:

1. `test_blend_modes.py::test_rhythm_lane_blend_mode_reaches_output` — pins the F3
   headline (structurally impossible today).
2. `…::test_accent_lane_blend_mode_reaches_output`.
3. `…::test_precedence_is_uniform_across_lanes` — encodes the chosen rule; the test
   name and docstring state which rule was chosen.
4. `…::test_no_cross_section_blend_contamination` — the F3 residual.
5. `…::test_unhonoured_lane_blend_mode_emits_diagnostic` (only if the chosen rule can
   leave one unhonoured; otherwise a test asserting it never can).

In `tests/unit/sequencer/display/`:

6. `test_effect_type_validation.py::test_unknown_effect_type_rejected_at_admission` —
   pins F8/M1's fix.
7. `…::test_known_effect_types_admitted` — regression guard over
   `registry.registered_types` (24 handlers at baseline; assert against the registry,
   not a hardcoded count).
8. `test_writer_warnings.py::test_fallback_surfaces_in_write_result_and_trace` — pins
   M1's "logged and nowhere else" defect. Assert on `WriteResult.warnings` **and** the
   trace entry, not on caplog.

Regression: the existing registry tests (`tests/unit/sequencer/display/effects/`) and
writer tests (`tests/unit/sequencer/display/export/`) must keep passing. If the
default-handler behavior changes, update
`tests/.../effects/test_registry.py` deliberately and explain the change in the PR
body — the review's standing rule is that a test which pins a defect must be changed,
not deleted quietly.

## Verification commands

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy .

uv run pytest tests/unit/sequencer/display/ -v
uv run pytest tests/unit/sequencer/display/composition/ -v
uv run pytest tests/unit/sequencer/display/export/ -v

# no NEW failures vs the baseline record in reviews/verification.md
uv run pytest tests/ -q

# render/export golden gate
uv run pytest tests/golden -v
```

LOCAL-ONLY: none. **Test budget: $0 — zero paid API calls.**

## Effort & risk

**Size: S–M** (phase review: ~1 hour for F3, ~2 hours for F8/M1, plus tests and the
decision record).

**Main risk: choosing the precedence rule badly and silently.** The review's exact
words are that the question "has never been answered, only avoided" — the failure mode
here is answering it implicitly again. *Mitigation*: the decision record is an
acceptance-blocking deliverable, and Test #3 encodes the rule by name so a future
change to it is a visible test change.

**Secondary risk: admission-time validation breaking existing recipes.** The recipe
corpus is gitignored (P5-F11) so the executor cannot survey real recipes for
unregistered types. *Mitigation*: land the validation with a clear error message and
run it against whatever tracked catalog exists after P1K-T3; if a tracked catalog
contains an unregistered type, that is a finding to report, not a reason to weaken the
check to a warning.

## Implementation handoff — 2026-08-16 (author pass; independent verification pending)

The owner explicitly authorized P3-T2 before the outstanding Phase 1P/2P/2K empirical
exits. This exception covers P3-T2 only: it does not waive those exits or authorize
P3-T3 or later Phase 3 work.

### Implemented contract

- Chose and implemented **lane wins** precedence. `LanePlan.blend_mode` now applies to
  every procedural and asset-overlay sub-layer emitted by BASE, RHYTHM, or ACCENT,
  independent of recipe metadata and lane iteration order. The module docstring and
  [durable decision](../../../../../memories/decisions/lane-blend-mode-overrides-recipe.md)
  record the rule and rejected alternative.
- Deleted the legacy `LayerAllocator.allocate` / `_COMPAT_LAYER_MAP` space after grep
  confirmed zero remaining production callers. `_layer_blend_modes` is written and read
  only with actual `allocate_sub_layer` / overlay indices.
- A non-Normal mode compacted into emitted xLights layer 0 produces a
  `CompositionDiagnostic`, because a base layer has nothing beneath it to blend with.
  Conflicting time-separated requests for one physical element/sub-layer likewise keep
  a deterministic first method and diagnose the later unhonoured request.
- `RecipeCompiler` resolves placeholder types, validates every resolved layer against
  its `HandlerRegistry`, and rejects the entire recipe before constructing any
  `RenderEvent` when a type is unregistered. Errors name the offending type, recipe,
  section/placement, and closest registered types.
- `DisplayRenderer` binds `RecipeCompiler` to the exact registry instance used for
  runtime dispatch, including caller-supplied custom registries. Direct compiler use
  defaults to the built-in runtime registry.
- Placeholder resolution and the retained default-handler path carry a structured
  `EffectSubstitution`. Dispatch appends a human-readable `EffectSettings.warning`;
  `XSQWriter` copies the structured record into the affected trace entry and increments
  `WriteResult.fallback_substitutions`; `RenderResult` and the sidecar payload expose the
  same count. The existing registry log warning remains.
- Existing registry fallback tests were deliberately strengthened to require structured
  substitution/warning data. The old multi-layer recipe test's unregistered `Sparkles`
  fixture was changed to the registered `Twinkle`; unknown types are now covered only by
  the explicit rejection/fallback tests.

### TDD and author verification evidence

- Before production edits, the new contract slice was **8 failed / 0 passed**. It
  discriminated RHYTHM/ACCENT structural loss, nonuniform precedence, cross-section
  contamination, the missing unhonoured diagnostic, missing registry admission, and
  missing warning/trace/count propagation.
- Post-fix focused P3-T2 plus directly affected registry/compiler tests: **27 passed**.
- Complete composition suite: **168 passed**. Complete display suite: **423 passed**.
- Display export regression suite: **30 passed**.
- Golden render/export gate: **73 passed / 8 skipped**; no golden artifact changed.
- Ruff format: **1,342 files clean**; Ruff lint with `--no-cache`: clean; mypy:
  **718 source files clean**.
- Full tests: **5,261 passed / 39 skipped / 9 warnings** in 96.00 seconds.

`make validate` was attempted and correctly stopped at its clean-worktree guard because
this author handoff necessarily contains uncommitted changes. Its check-only
formatter/linter/type-checker and full-test equivalents above all passed.

No network, live provider, paid API, xLights, or audio operation was performed.
Independent verification is required before integration; this author does not approve
their own work.

### File manifest

Production:

- `packages/twinklr/core/sequencer/display/composition/engine.py`
- `packages/twinklr/core/sequencer/display/composition/layer_allocator.py`
- `packages/twinklr/core/sequencer/display/composition/recipe_compiler.py`
- `packages/twinklr/core/sequencer/display/effects/protocol.py`
- `packages/twinklr/core/sequencer/display/effects/registry.py`
- `packages/twinklr/core/sequencer/display/export/writer.py`
- `packages/twinklr/core/sequencer/display/models/render_event.py`
- `packages/twinklr/core/sequencer/display/renderer.py`

Tests:

- `tests/unit/sequencer/display/composition/test_blend_modes.py`
- `tests/unit/sequencer/display/composition/test_layer_allocator.py`
- `tests/unit/sequencer/display/composition/test_recipe_compiler.py`
- `tests/unit/sequencer/display/effects/test_registry.py`
- `tests/unit/sequencer/display/test_effect_type_validation.py`
- `tests/unit/sequencer/display/test_writer_warnings.py`

Campaign truth and decision record:

- `changes/ACTIVE.md`
- `changes/twinklr-reactivation-review/build/plan/06-phase-3-show-convergence.md`
- `changes/twinklr-reactivation-review/build/plan/HANDOFF.md`
- this specification
- `context/current-state.md`
- `memories/INDEX.md`
- `memories/decisions/lane-blend-mode-overrides-recipe.md`

Still open by explicit non-goal: parameter range validation/settings escaping,
`resolved_color`, `timing_offset_beats`, layer `mix` consumption beyond its existing
compiler behavior, and moving-head changes. P3-T5/P3-T8 and the remaining display review
tasks continue to own those boundaries.
