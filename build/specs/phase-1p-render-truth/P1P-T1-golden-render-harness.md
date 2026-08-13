# P1P-T1 — Golden render harness

Phase: 1P (Render Truth) · Lane: G (golden first) · Executor: opus · Verifier: opus · Depends on: P0-T4

## Objective

Before any render behavior changes, the repository gains a gate that can *see* the
render output: the existing 587-LOC `.xsq` validator runs in CI, a set of pinned golden
settings-strings exists for 2–3 fixture rigs, and the first XSQ parse→export round-trip
test in the repository's history exists. After this task, every Lane-R change produces a
reviewable golden diff, and a regression that zeroes a channel, flattens a curve, or
drops a section fails a test instead of shipping.

## Evidence & background

Findings: **ST-7**, **P4-M8**, **P4-F22**, **P5-V1**, **CC-7**.

Line numbers below are hints from baseline `aa8d325`; re-verify symbol locations before
editing (per the plan overview: *"Executors must re-verify cited line numbers before
editing (the tree will drift as phases land) — specs cite symbol + file, with line
numbers as hints only."*).

**The validator already exists and is unit-tested (P4-M8, verbatim from
`reviews/phases/moving-heads-rendering.md` §11b):**

> `scripts/validation/_core/mh_xsq_validation.py` (587 LOC, unit-tested) already parses
> emitted DMX settings, flags all-zero effects as CRITICAL, and cross-checks
> shutter/colour/gobo mappings — but runs only post-hoc via
> `scripts/validation/validate_artifacts.py` and is absent from `make validate` and CI.
> This converts §13 step 1 from "build a validator" into "wire an existing one in".

Confirmed present in the current tree: 587 lines; the all-zero CRITICAL check emits
`"❌ CRITICAL: {zero_percentage:.1f}% of effects have ALL ZERO values ({all_zero_effects}/{effects_with_data}) - NO ACTUAL MOVEMENT IMPLEMENTED"`;
covered by `tests/unit/scripts/validation/test_mh_xsq_core_validation.py`; driven by
`scripts/validation/validate_artifacts.py`.

**Why this must land first (P4-F22, verbatim):**

> A golden test over `DmxSettingsBuilder.build_settings_string` for one 4-bar section
> would still have caught P4-F1, F3, F7, F9, F10, M1, M2 and the effects of F5 and F6 —
> and the existing validator's all-zero check would plausibly have caught P4-F3 and
> P4-M1 on any real run. **This must land before any of the fixes, so the fixes are
> verifiable.**

**The shutter emitted-bytes test spec (P4-F3 `[V]`, verbatim — this is the exact test
this task must implement):**

> render one 4-bar section twice against two otherwise-identical fixture configs — one
> with `shutter_channel=6`, one with `shutter_channel=17` — and assert on the emitted
> settings string that (a) the first contains `E_SLIDER_DMX6=0`, and (b) the second
> contains no `E_SLIDER_DMX17` token. That distinguishes "actively shuttered closed"
> from "left to the console" and settles the no-audio/no-light question without needing
> physical hardware.

Note the only fixture configuration tracked in the repository today uses
`shutter_channel=17` (`tests/unit/config/test_fixtures.py:399`) — i.e. outside the
emitted 1–16 window — which is why both arms of the test are required.

**Round-trip absence (P5 §V4, verbatim):**

> There is **no sample `.xsq` anywhere in the tree**, no golden file, no fixture, no
> round-trip test.

**CC-7 (test-system integrity)** records "zero round-trip tests" as a repo-wide defect.

Relevant symbols (verified present):
- `packages/twinklr/core/sequencer/moving_heads/export/dmx_settings_builder.py` —
  `DmxSettingsBuilder.build_settings_string` (`:42`), the `E_SLIDER_DMX` emit loop
  (`:75-83`), `_calculate_max_channel` (`:233`), curve-point rounding (`:291-293`).
- `packages/twinklr/core/sequencer/moving_heads/xsq_export.py` — `export_to_xsq` (`:28`),
  template branch (`:53-56`), fresh branch with `version="2024.10"`, `media_file=""`
  (`:67-68`).
- `packages/twinklr/core/formats/xlights/sequence/timeline.py` — `build_timeline_tracks`
  (`:48`), `_build_beats_track` / `_build_bars_track`.
- `scripts/validation/_core/mh_xsq_validation.py`, `scripts/validation/validate_artifacts.py`.

## Current behavior

- No test anywhere asserts the content of a generated settings string, an
  `E_VALUECURVE_DMX` payload, or a byte of `.xsq`.
- The only end-to-end render test,
  `tests/unit/sequencer/moving_heads/test_rendering_pipeline.py::test_render_returns_segments`
  (`:262`), **patches `compile_template` with a `MagicMock`**, so it never executes the
  compiler, handlers, curves, or exporter.
- `dmx_settings_builder.py` and `xsq_export.py` have **zero direct tests**.
- The validator runs only when a human invokes `scripts/validation/validate_artifacts.py`
  against an artifact directory; it is not in `make validate` and not in CI.
- No `.xsq` fixture is tracked in git, so nothing can be parsed→exported→compared.

## Target behavior

1. `mh_xsq_validation` is importable and callable from the test suite (not only from the
   `scripts/` driver), and runs as part of the CI pipeline created in P0-T4.
2. A golden-file test suite exists that, for each tracked fixture rig (delivered by
   P1P-T2) and a deterministic plan fixture, renders and compares the **full emitted
   settings string per effect** against a committed golden file, with a documented
   regeneration command.
3. The shutter-channel test above exists and passes at baseline (it pins today's
   behavior; P1P-T6 will change one of its expectations and must update the golden).
4. An `.xsq` parse→export round-trip test exists over a tracked minimal `.xsq` fixture,
   asserting the exporter's output re-parses and that the enumerated P5-F5 survivable
   fields survive.

**Non-goals.** Do not fix any render defect in this task — no change to handlers,
scheduler, exporter policy, or curve math. Goldens at the end of this task encode
**today's (broken) behavior**; that is the point. Do not wire the validator's severity
into a build failure for pre-existing CRITICALs on legacy artifacts (see acceptance
criteria for the exact gating rule).

## Implementation approach

Files/symbols to touch:
- `scripts/validation/_core/mh_xsq_validation.py` — make it importable without side
  effects if it is not already; do **not** rewrite its checks.
- New: `tests/golden/` (or `tests/integration/render_golden/` — pick one and be
  consistent) holding golden `.txt`/`.json` files plus the test module.
- New: a small pytest helper that renders a deterministic plan through
  `RenderingPipeline` (`packages/twinklr/core/sequencer/moving_heads/pipeline.py:134`)
  with a fixed `BeatGrid` and a tracked fixture config, and returns per-effect settings
  strings.
- `Makefile` and the P0-T4 CI workflow — add the golden suite and the validator run.
- `pytest.ini`/`pyproject.toml` markers if a `golden` marker is introduced.

Design decisions already made (do not relitigate):
- **Wire the existing validator; do not write a new one.** (P4-M8 / §13 step 1.)
- Golden comparison is on the **settings string**, not on rendered XML only — the
  settings string is where P4-F1/F3/F9/F10/M1/M2 are visible.
- Goldens are text files committed to git with a `--regen` mechanism (env var or pytest
  flag), so a Lane-R diff shows the behavioral change in review.
- The round-trip fixture is a **minimal hand-built `.xsq`**, small enough to review;
  it is the repository's first tracked `.xsq`.

Sequencing constraints that apply (copied verbatim from `build/plan/00-overview.md`):

> `make validate` equivalents (check-only forms until P0-T4 lands the guard) must pass
> at every merge; golden tests (once P1P-T1 exists) must pass for any lane touching
> render/export code.

> **Verification currency**: evidence in specs is from baseline `aa8d325`. Executors
> must re-verify cited line numbers before editing (the tree will drift as phases land)
> — specs cite symbol + file, with line numbers as hints only.

Lane note from the phase plan: *"Lane G (golden first): T1 → T2 (harness before any
render change; everything in Lane R diffs against it)."* Merge order at phase end is
**G → R → A → I → D**.

## Acceptance criteria

- [ ] `scripts/validation/_core/mh_xsq_validation.py` is invoked by at least one test in
      `tests/` and by the CI pipeline; the existing
      `tests/unit/scripts/validation/test_mh_xsq_core_validation.py` still passes
      unchanged.
- [ ] Golden suite renders **without mocking `compile_template`** — the compiler,
      handlers, curves, and exporter all execute. A test asserting the golden path does
      not import `unittest.mock` for the render call.
- [ ] For each rig from P1P-T2, a golden file exists containing the complete settings
      string of every emitted effect for the deterministic plan fixture.
- [ ] **Shutter test (both arms, exact assertions):** with an otherwise-identical
      fixture config,
      `shutter_channel=6` → the emitted settings string **contains** the token
      `E_SLIDER_DMX6=0`; `shutter_channel=17` → the emitted settings string **contains
      no** `E_SLIDER_DMX17` token.
- [ ] Round-trip test: `XSQParser.parse(fixture) → exporter → parse again` succeeds, and
      asserts (a) effect-level unknown attributes survive (`Effect.parameters`
      round-trip, the one documented survivor in P5-F5 item 7) and (b) the emitted head
      contains a non-empty `mediaFile` (this is the assertion that will catch the
      `media_file=""` self-fatal fresh-emit branch when P1P-T11 turns it on).
- [ ] The golden suite is deterministic: two consecutive runs produce byte-identical
      output; no timestamps, no UUIDs, no dict-ordering dependence in the golden files.
- [ ] Gating rule implemented: the validator's findings on the **golden-suite render**
      fail CI; the validator's findings on arbitrary legacy artifacts do not gate.
- [ ] Baseline goldens are committed as-is and the commit message records that they
      encode known-defective output (naming P4-F1/F3/M1/M2 as expected-present in the
      baseline goldens).

**Golden-diff expectation for this task (BEFORE/AFTER):**

```
BEFORE: no golden files exist; no test reads an emitted settings string.
AFTER : tests/golden/<rig>/<section>.settings.txt exists and contains, per effect,
        a full E_* settings string. On the 4-head reference rig, the committed
        baseline goldens are expected to show (all defects to be fixed later):
          - E_SLIDER_DMX{1..16} present, every unchoreographed channel = 0   (P4-F3)
          - identical movement curves regardless of preset_id                (P4-F1)
          - dimmer values reaching 0 rather than the declared floor 60        (P4-M1)
          - blackout templates emitting 255 under ENERGETIC                   (P4-M2)
          - value-curve points at 2-decimal resolution                        (P4-F10)
        These are recorded, not fixed, by this task.
```

## Tests

TDD is natural here: write the shutter test and the round-trip test first (both fail —
one because no fixture rigs exist yet, one because no `.xsq` fixture exists), then build
the harness until they pass.

| Test | Behavior pinned |
|---|---|
| `test_settings_string_golden[rig]` | Full emitted settings string per effect for a deterministic plan; any render change shows as a reviewable diff |
| `test_shutter_channel_6_is_actively_zeroed` | `E_SLIDER_DMX6=0` present when shutter is mapped inside the emitted window |
| `test_shutter_channel_17_is_not_emitted` | No `E_SLIDER_DMX17` token when shutter is mapped outside the window |
| `test_xsq_round_trip_preserves_effect_parameters` | Parse→export→parse keeps unknown effect attributes |
| `test_xsq_round_trip_media_file_non_empty` | Exported head carries a non-empty `mediaFile` (guards the P5 self-fatal fresh branch) |
| `test_validator_runs_on_golden_render` | The 587-LOC validator executes against freshly rendered output inside the test suite |
| `test_golden_render_is_deterministic` | Two renders of the same fixture produce identical bytes |

## Verification commands

```bash
# check-only gates (no source mutation)
uv run ruff format --check .
uv run ruff check .
uv run mypy .

# the new suite
uv run pytest tests/golden -v
uv run pytest tests/unit/scripts/validation/test_mh_xsq_core_validation.py -v

# determinism proof
uv run pytest tests/golden -q && uv run pytest tests/golden -q
git status --porcelain   # must be empty: goldens must not be rewritten by a run

# regeneration path exists and is documented
uv run pytest tests/golden --regen-goldens -q && git diff --stat
```

No LOCAL-ONLY steps. No paid API calls: the plan fixture is deterministic and
LLM-free (delivered by P1P-T2).

## Effort & risk

**Effort: M.**

Main risk: **golden brittleness** — goldens that capture incidental ordering or
floating-point noise will fail spuriously and get disabled, which would defeat the whole
phase. Mitigation: sort channels/effects deterministically before writing; pin
`n_samples` (currently a fixed `64` at `sequencer/models/context.py`) explicitly in the
fixture rather than relying on the default; assert on the exact emitted string rather
than re-deriving it; include the determinism test above as a first-class acceptance
criterion.

Secondary risk: making `mh_xsq_validation.py` importable pulls `scripts/` onto the test
import path in a way that upsets P0-T2's structural test repair. Mitigation: import via
an explicit path-based helper or a thin `tests/` shim; do not restructure `scripts/`.
