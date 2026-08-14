# P1P-T3 — Intensity + movement-library repair

Phase: 1P (Render Truth) · Lane: R (render repair, serial) · Executor: opus · Verifier: opus · Depends on: P1P-T1, P1P-T2

## Objective

Make movement intensity reach the output. Today every movement in every show renders at
`Intensity.SMOOTH` regardless of section energy or preset, and the integration test suite
encodes that as correct. This task reconnects the intensity axis, fills in the movement
library's missing intensity data so the reconnection does not crash, fixes the
frequency/excursion inversion that would otherwise make the reconnection *worse* than the
defect, fixes the end-of-segment snap-back, and rewrites the test that pins the defect.

**These four items land in one change. This is a hard constraint, not a preference —
see "Sequencing constraints" below.**

## Evidence & background

Findings: **CF-1** = **P4-F1 / P4-F1a / P4-M4 / P4-M6**, plus **P4-M5**. This is one of
the review's two CRITICALs; the verifier's verdict was *"F1 (CRITICAL, held): overwrite
unconditional, no surviving path"*.

Line numbers are hints from baseline `aa8d325`. Re-verify before editing.

### Defect 1 — the intensity overwrite (P4-F1, CRITICAL). Verbatim:

> `handlers/movement/default.py:81`:
>
> ```python
> def generate(self, params, n_samples, cycles, intensity: Intensity) -> MovementResult:   # :48-54
>     ...
>     intensity = params.get("intensity", Intensity.SMOOTH)                                 # :81
> ```
>
> The caller-supplied `intensity` parameter is unconditionally overwritten by a lookup in
> `params`. `params` is `movement_params`, built at `compile/step_compiler.py:95` as
> `dict(step.movement.params)` plus `base_pan_norm`, `base_tilt_norm`, `calibration`,
> `geometry`, and (injected at `handlers/registry.py:207`) `movement_pattern` — it never
> contains an `"intensity"` key. The real value arrives via the parameter at
> `step_compiler.py:113` (`intensity=step.movement.intensity`).

> **Impact.** `DEFAULT_MOVEMENT_PARAMS` (`libraries/movement.py:61-67`) maps intensity to
> `(amplitude, frequency, center_offset)`; pinned to SMOOTH that is always
> `(0.4, 0.5, 0.5)`. Consequences: (1) the auto-synthesized energy preset
> (`pipeline.py:199-206`, the path taken for 33/37 templates) has **zero effect on
> movement**; (2) the hand-authored `gentle`/`intense` presets on 4 templates affect
> movement only through their `cycles` patch, not intensity; (3) movement amplitude and
> frequency are constant across the entire song regardless of section energy.

Re-verified in the current tree: `handlers/movement/default.py:81` is exactly
`intensity = params.get("intensity", Intensity.SMOOTH)`, immediately followed by
`:82 categorical_params_set = pattern.categorical_params or DEFAULT_MOVEMENT_PARAMS` and
`:83 categorical_params = categorical_params_set[intensity]` — an **unguarded**
subscript. `DEFAULT_MOVEMENT_PARAMS` currently holds all five intensities:
`SLOW(0.2, 0.25, 0.5)`, `SMOOTH(0.4, 0.5, 0.5)`, `DRAMATIC(0.65, 1.5, 0.5)`,
`FAST(0.8, 2.0, 0.5)`, `INTENSE(1.0, 3.0, 0.5)`.

### Defect 2 — the data gap that makes a one-line fix crash (P4-F1a). Verbatim:

> **P4-F1a (blocking co-requisite) — larger than first stated. [V]** The movement handler
> indexes `categorical_params_set[intensity]` at `:83` **with no membership guard**,
> unlike the dimmer handler which guards at `handlers/dimmers/default.py:86-89`. AST
> census of all `MovementPattern` constructions in `libraries/movement.py`: **29
> patterns; 2 declare no `categorical_params` at all** (falling back to the complete
> 5-entry `DEFAULT_MOVEMENT_PARAMS`), **10 declare exactly one entry** (`sweep_ud` `:270`,
> `circle`, `figure8`, `tilt_bounce` `:382`, `groove_sway`, `trampoline`, `laser_snap`
> `:438`, `stomp`, `fan_iris`, `radial_fan`), and 17 declare two. **Only 2 of 29 patterns
> cover all five intensities — so a naive fix at `:81` would raise `KeyError` for 27 of
> 29 patterns** on any non-SMOOTH intensity. The fix is therefore not one line: it is
> *guard + data fill-in across the movement library*, and the data half is the bulk of
> the work (choosing amplitude/frequency/center values for ~100 missing intensity entries
> is a choreographic judgement, not a mechanical edit).

**Independently re-derived by AST against the current tree during spec authoring — the
census is exact and the executor must treat this table as the work list:**

| Category | Count | Pattern ids | Intensities declared |
|---|---|---|---|
| No `categorical_params` | 2 | `sweep_lr` (`:261`), `hold` (`:315`) | — (falls back to the complete 5-entry `DEFAULT_MOVEMENT_PARAMS`) |
| Exactly one entry | 10 | `sweep_ud` (`:270`), `circle` (`:280`), `figure8` (`:290`), `tilt_bounce` (`:382`), `groove_sway` (`:392`), `trampoline` (`:402`), `laser_snap` (`:438`), `stomp` (`:466`), `fan_iris` (`:557`), `radial_fan` (`:567`) | `SMOOTH` only |
| Exactly two entries | 17 | `infinity`, `random_walk`, `pan_shake`, `tilt_rock`, `bounce`, `pendulum`, `accent_snap`, `pop_lock`, `hit`, `wave_horizontal`, `wave_vertical`, `zigzag`, `spiral`, `diagonal_sweep`, `corner_to_corner`, `dual_sweep`, `cross_pattern` | `SMOOTH` + `DRAMATIC` |

Missing-entry arithmetic: `10 × 4 + 17 × 3 = 91` entries to author (the review's
"~100 missing intensity entries"). **27 of 29 patterns KeyError on `SLOW`, `FAST`, or
`INTENSE`; the 17 two-entry patterns additionally survive `DRAMATIC` and no other.**

### Defect 3 — frequency silently changes excursion (P4-M6). Verbatim:

> `frequency` is passed to the curve generator (`handlers/movement/default.py:281`) where
> it scales cycles, and the result is then normalized by `center_curve`
> (`curves/semantics.py:36-37`), which rescales the sampled window's actual min/max to the
> full `[0,1]` range. When `frequency < 1` the window contains less than a full
> oscillation, so the observed min/max span is *narrower* — and `center_curve` stretches
> that partial arc back to full range. **Halving the frequency therefore roughly doubles
> the physical excursion**, and the fixture ends the step parked at an extreme rather than
> near centre.
>
> Because `DEFAULT_MOVEMENT_PARAMS` pairs low intensity with low frequency
> (`SLOW: frequency=0.25`, `SMOOTH: 0.5` — `libraries/movement.py:62-63`), the intent is
> inverted: `SLOW` produces the *largest* swing. Currently masked by P4-F1 (everything is
> pinned to SMOOTH), so this becomes visible **the moment P4-F1 is fixed** — it must be
> addressed in the same change or the fix will make output worse.

### Defect 4 — end-of-segment snap-back (P4-M5). Verbatim:

> `_movement_post_process` (`curves/functions/movement.py:21-22`) calls `ensure_loop_ready`,
> which in `"append"` mode adds `CurvePoint(t=1.0, v=points[0].v)` whenever the curve's end
> value differs from its start (`curves/semantics.py:70-77`). For any movement whose sampled
> window does not close on its starting value — which includes every non-integer `cycles`
> setting and every curve family whose period does not divide the window — the emitted curve
> therefore jumps from wherever the motion ended back to the **start** value across a single
> sample interval, `1/64` of the segment. On a physical head that is a full-excursion snap
> rather than a continuation. It affects most of the movement library and is invisible in the
> curve statistics because the value range is unchanged. Interacts with P4-F14: the exporter's
> `t=1.00` anchor (`export/dmx_settings_builder.py:307-310`) preserves it into the `.xsq`.

### Defect 5 — the test that pins the defect (P4-M4 / P4-F1 `[V]`). Verbatim:

> **[V] The defect is not untested — it is PINNED BY A TEST.** … 
> `tests/integration/test_handler_categorical_params.py` exercises
> `DefaultMovementHandler.generate` four times (`:23`, `:51`, `:84`, `:112`) and **every call
> passes intensity twice** — once as `params={"intensity": …}` and once as the `intensity=`
> argument (e.g. `:34` with `:43`, `:63` with `:69`). Production supplies only the argument.
> So `test_handler_intensity_affects_curves_currently` (`:51`) asserts that higher intensity
> yields more curve energy **and passes**, but only because the test itself injects the
> `params` key that production never sets. Two of the four tests are literally named
> `…_currently` … **Remediation must change this test, not merely add one** — a fix that
> keeps these tests green has not fixed anything.

Re-verified: the file exists and contains `"intensity": Intensity.FAST` at `:35` alongside
`intensity=Intensity.FAST` at `:43`, and `test_handler_intensity_affects_curves_currently`
at `:51`.

### Trap to avoid (P4-F13, verbatim — the amplitude kwarg is inert):

> The handler **deliberately does not pass amplitude to the curve generator** —
> `curve_params` (`handlers/movement/default.py:280-286`) contains only `cycles`,
> `frequency` and filtered base params, with an explicit comment at `:283-284`:
> *"amplitude is NOT passed here — it's applied to the generated curve below"*. …
> The finding is retained because it is a **trap for the P4-F1 fix**: anyone restoring
> intensity plumbing who assumes the curve-level `amplitude` kwarg is the lever will find
> it silently inert for these five families. … the working lever is the scaling path
> (`handlers/movement/default.py:301-330`).

Re-verified: the comment at `:284` reads
`# NOTE: amplitude is NOT passed here - it's applied to the generated curve below`.

## Current behavior

1. Every movement curve in every rendered show uses `MovementCategoricalParams(amplitude=0.4, frequency=0.5, center_offset=0.5)` (SMOOTH), whatever the plan says.
2. Passing any other intensity through today's code would `KeyError` on 27 of 29 patterns.
3. `frequency < 1` widens rather than narrows the physical excursion, so the SLOW/SMOOTH
   intent is inverted the moment (1) is fixed.
4. Most movement segments end with a full-excursion jump back to the start value inside
   the final 1/64 of the segment, preserved into the `.xsq` by the exporter's `t=1.00`
   anchor.
5. Four integration tests pass **because** they supply a `params["intensity"]` key that
   production never sets.

## Target behavior

1. `DefaultMovementHandler.generate` uses the **caller-supplied** `intensity` argument.
   The `params`-key lookup is removed, not merely reordered. If a params-key override is
   retained for any reason, the argument must win and a test must prove it.
2. The subscript at `:83` is **guarded** (mirroring the dimmer handler's guard at
   `handlers/dimmers/default.py:86-89`), so an unknown intensity degrades to a defined
   fallback rather than raising.
3. All 29 movement patterns resolve for all five `Intensity` members without falling back:
   the 10 single-entry and 17 two-entry patterns gain the missing entries (91 total),
   authored as choreographic judgements consistent with the pattern's character.
4. Intensity monotonically increases movement energy: for every pattern, curve energy at
   `SLOW ≤ SMOOTH ≤ DRAMATIC ≤ FAST ≤ INTENSE` (see "Tests" for the exact metric), and
   **physical excursion does not invert** — `SLOW` must not produce a larger swing than
   `INTENSE`.
5. Movement segments no longer end with a full-excursion snap to the start value.
6. `tests/integration/test_handler_categorical_params.py` no longer supplies
   `params["intensity"]` anywhere, and its assertions hold against production's real call
   shape.

**Non-goals (do not creep):**
- Do **not** fix the preset space (P4-F8) — that is P1P-T5.
- Do **not** touch the time grid (P4-F2/M3) — that is P1P-T4.
- Do **not** touch `center_offset`/calibration annihilation (P4-F9) — that is P1P-T5.
- Do **not** fix `FIGURE8`-traces-a-circle (P4-M7) or the three straight-line Lissajous
  patterns (P4-F12) here unless a fill-in entry cannot be authored without it; if so,
  record it and keep the change minimal.
- Do **not** delete dead curve modules (P4-F20) — Phase 4 debt task.

## Implementation approach

Files/symbols to touch:
- `packages/twinklr/core/sequencer/moving_heads/handlers/movement/default.py` — the
  overwrite at `:81`, the unguarded subscript at `:83`, the frequency handling around
  `:280-286`, the post-hoc amplitude scaling path at `:301-330`.
- `packages/twinklr/core/sequencer/moving_heads/libraries/movement.py` — the 27 patterns
  needing entries; `DEFAULT_MOVEMENT_PARAMS` stays as-is (it is already complete).
- `packages/twinklr/core/curves/functions/movement.py` (`_movement_post_process`) and/or
  `packages/twinklr/core/curves/semantics.py` (`center_curve`, `ensure_loop_ready`) for
  P4-M6 and P4-M5.
- `tests/integration/test_handler_categorical_params.py` — rewrite.

Design decisions already made (do not relitigate):
- **The working amplitude lever is the post-hoc scaling path**, not the curve generator's
  `amplitude` kwarg (P4-F13). Do not "restore" the kwarg.
- **P4-M6 is fixed at the normalization seam, not by re-tuning the frequency table.**
  `center_curve`'s rescale-to-full-range is what converts a frequency change into an
  excursion change; the fix must stop excursion from depending on frequency, then the
  existing `(amplitude, frequency)` pairings mean what they say. Re-tuning the table to
  compensate would leave the inversion latent for every future entry — including the 91
  new ones this task authors.
- **P4-M5 is fixed by not synthesizing a discontinuity**: either close the curve
  smoothly or stop appending the `t=1.0` start-value anchor for non-looping segments.
  Whichever is chosen, phase-shifted chase curves must still be loop-safe — P4-F14 notes
  `ensure_loop_ready` is what currently masks the non-cyclic interpolation trap in
  `curves/phase.py`, so removing it wholesale is not acceptable.
- **The pinning test is rewritten, not supplemented.** Per P4-M4: *"a fix that leaves
  these tests green has not fixed P4-F1."*

Sequencing constraints (copied verbatim from `changes/twinklr-reactivation-review/build/plan/00-overview.md`):

> P4-F1 intensity fix + F1a data fill-in + P4-M6 frequency-amplitude land **together**
> (P1P-T3).

> `make validate` equivalents (check-only forms until P0-T4 lands the guard) must pass
> at every merge; golden tests (once P1P-T1 exists) must pass for any lane touching
> render/export code.

> **Verification currency**: evidence in specs is from baseline `aa8d325`. Executors
> must re-verify cited line numbers before editing (the tree will drift as phases land)
> — specs cite symbol + file, with line numbers as hints only.

And from `changes/twinklr-reactivation-review/build/plan/02-phase-1p-render-truth.md`:

> **Lane R (render repair, serial — shared files in `sequencer/moving_heads/` +
> `curves/`)**: T3 → T4 → T5 → T6.

> T3/T4/T5 are the review's CRITICALs: verifier is opus, and acceptance criteria must
> quote the verified defect mechanics (from `reviews/phases/moving-heads-rendering.md`)
> so the executor cannot "fix" a different reading of the bug.

## Acceptance criteria

- [ ] `handlers/movement/default.py` contains **no** `params.get("intensity", ...)`
      assignment that shadows the `intensity` argument. Verifiable by grep.
- [ ] The categorical-params subscript is guarded; an intensity absent from a pattern's
      table cannot raise `KeyError`.
- [ ] A test constructs every one of the 29 `MovementPattern`s and calls `generate` for
      all five `Intensity` members: **145 calls, zero exceptions, zero fallbacks to
      `DEFAULT_MOVEMENT_PARAMS` for the 27 patterns that declare their own table.**
- [ ] Monotonic energy per pattern (see Tests for the metric): `SLOW ≤ SMOOTH ≤ DRAMATIC
      ≤ FAST ≤ INTENSE`, with at least a strict increase between `SLOW` and `INTENSE`.
- [ ] **Excursion is not inverted:** for a fixed pattern and fixed base pose, peak-to-peak
      normalized excursion at `SLOW` is **strictly less than** at `INTENSE`. (This is the
      P4-M6 acceptance test; it fails on today's code with the intensity fix alone.)
- [ ] No emitted movement curve contains a final-sample jump larger than the largest
      inter-sample delta elsewhere in the same curve (P4-M5 acceptance).
- [ ] `tests/integration/test_handler_categorical_params.py` contains **zero**
      occurrences of `"intensity"` as a dict key. Verifiable by grep. Its assertions pass
      against production's call shape (intensity supplied only as the argument).
- [ ] All 37 templates compile without exception for the 4-head and 8-head rigs (this
      closes review §12 runtime item 7).
- [ ] `make validate` check-only equivalents pass; golden suite regenerated with reviewed
      diffs.

**Golden-diff expectation (BEFORE/AFTER), 4-head reference rig, deterministic plan:**

```
BEFORE (baseline goldens from P1P-T1/T2):
  Every section's E_VALUECURVE_DMX pan/tilt payload is byte-identical across
  preset_id=CHILL / MODERATE / ENERGETIC — because all three resolve to SMOOTH
  (amplitude=0.4, frequency=0.5). Curve peak-to-peak is the same in an intro
  section and a drop section.
  Each movement value-curve ends with a jump back to its first value in the
  final 1/64 of the segment.

AFTER:
  - CHILL (→SLOW), MODERATE (→SMOOTH), ENERGETIC (→DRAMATIC) produce THREE
    DISTINCT pan/tilt payloads per section. Diff shows changed Values= strings
    on every movement effect in the CHILL and ENERGETIC sections.
  - Peak-to-peak excursion ORDERS correctly: the drop section's payload spans a
    wider normalized range than the intro section's. (Before the M6 fix in the
    same change, this diff would show the OPPOSITE ordering — that inversion
    appearing in the golden diff is a FAIL, not an accepted change.)
  - Final-sample snap-back removed: the last two points of each movement curve
    differ by no more than the curve's typical inter-sample delta.
  - UNCHANGED in this diff (they belong to later tasks): E_SLIDER_DMX zero-fill
    on unchoreographed channels (P1P-T6), section start times (P1P-T4), dimmer
    floors and BLACKOUT values (P1P-T5), 2-dp curve rounding (P1P-T5/T6 scope).
    Any movement in those tokens means this task overreached.
```

## Tests

TDD: write the 145-call matrix test and the excursion-inversion test **first**; both fail
at baseline (the first with `KeyError`, the second because SLOW swings widest).

| Test | Behavior pinned |
|---|---|
| `test_generate_uses_argument_intensity_not_params_key` | The argument is authoritative; supplying a conflicting `params["intensity"]` cannot change the result |
| `test_all_patterns_all_intensities_resolve` (29 × 5) | P4-F1a data fill-in is complete; no `KeyError`, no silent fallback |
| `test_intensity_monotonic_curve_energy[pattern]` | Higher intensity ⇒ more curve energy (metric: sum of absolute first differences over the sampled curve, i.e. total variation) |
| `test_slow_excursion_less_than_intense_excursion[pattern]` | **P4-M6**: frequency no longer inverts physical excursion (metric: `max(v) - min(v)`) |
| `test_no_terminal_snapback[pattern]` | **P4-M5**: final inter-sample delta ≤ max non-terminal inter-sample delta |
| `test_handler_categorical_params.py` (rewritten) | The four existing behaviors, asserted against production's real call shape; the `…_currently` names retired |
| `test_all_37_templates_compile[rig]` | Review §12 item 7: no template raises for the 4-head or 8-head rig |
| Golden suite (P1P-T1) | Reviewed BEFORE/AFTER diff as specified above |

## Verification commands

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy .

uv run pytest tests/integration/test_handler_categorical_params.py -v
uv run pytest tests/unit/sequencer/moving_heads -v
uv run pytest tests/golden -v

# defect-specific greps the verifier runs
grep -n 'params.get("intensity"' packages/twinklr/core/sequencer/moving_heads/handlers/movement/default.py   # expect: no match
grep -c '"intensity"' tests/integration/test_handler_categorical_params.py                                    # expect: 0

# census re-derivation (must report 29 patterns, 0 with fewer than 5 intensities)
uv run python -c "
import ast
t=ast.parse(open('packages/twinklr/core/sequencer/moving_heads/libraries/movement.py').read())
n=0; bad=[]
for x in ast.walk(t):
    if isinstance(x,ast.Call) and getattr(x.func,'id','')=='MovementPattern':
        n+=1; kw={k.arg:k.value for k in x.keywords}
        c=kw.get('categorical_params')
        if isinstance(c,ast.Dict) and len(c.keys)<5: bad.append((x.lineno,len(c.keys)))
print('patterns',n,'incomplete',bad)"
```

No LOCAL-ONLY steps. No paid API calls: everything runs off the deterministic plan
fixture from P1P-T2.

## Effort & risk

**Effort: L** — 91 authored data entries plus four coupled code fixes.

**Main risk: the data half is choreographic judgement, and getting it wrong is invisible
to tests.** A mechanically-generated table (e.g. linear interpolation of amplitude) will
pass every assertion in this spec and still look wrong on real fixtures. Mitigation: (a)
derive each pattern's five entries from that pattern's own character and its existing
SMOOTH/DRAMATIC anchors rather than from a global formula; (b) keep
`DEFAULT_MOVEMENT_PARAMS`' ratios as the sanity envelope
(SLOW 0.2 / SMOOTH 0.4 / DRAMATIC 0.65 / FAST 0.8 / INTENSE 1.0 amplitude); (c) the
opus verifier reviews the authored table as data, not just the tests; (d) the golden diff
for a CHILL and an ENERGETIC section is inspected by eye.

**Second risk: fixing P4-M6 at the `center_curve` seam changes every movement curve in
the library at once**, including patterns whose current look someone may like.
Mitigation: the golden diff makes the full blast radius visible before merge, and the
monotonicity/excursion tests define the intended direction. If the seam fix proves
larger than expected, the fallback is to make the normalization amplitude-preserving
only on the movement path (`_movement_post_process`) rather than in shared
`curves/semantics.py`, keeping the display path untouched — but the inversion **must**
be gone before this task merges, per the sequencing constraint.

**Third risk: touching `ensure_loop_ready` for P4-M5 re-opens the latent non-cyclic
interpolation trap** documented in P4-F14. Mitigation: keep the `t=1.0` point present for
phase-shifted (chase) curves; only its *value* is at issue.
