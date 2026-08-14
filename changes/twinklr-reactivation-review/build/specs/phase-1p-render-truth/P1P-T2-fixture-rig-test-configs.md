# P1P-T2 — Fixture-rig test configs

Phase: 1P (Render Truth) · Lane: G (golden first) · Executor: sonnet · Verifier: sonnet · Depends on: P1P-T1

## Objective

Give the golden harness something real and stable to render against: 2–3 tracked fixture
rig configurations (a 4-head rig matching the author's, an 8-head rig, and a rig whose
shutter sits above channel 16) plus a tiny deterministic `ChoreographyPlan` fixture, so
golden diffs are reproducible with no audio decode, no network, and no LLM call.

## Evidence & background

Findings: **P4 census** (`reviews/phases/moving-heads-rendering.md` §10), **P7-M1**.

**Why more than one rig is required.** From P4-F3 `[V]`, verbatim:

> The only fixture configuration tracked in this repository puts the shutter at channel
> 17 (`tests/unit/config/test_fixtures.py:399`, `shutter_channel=17`) — outside the
> window, so for that profile no `E_SLIDER_DMX17` is emitted at all and the
> console/model default governs. The no-light outcome therefore holds for fixtures whose
> shutter is mapped within 1–16 (common on 12- and 16-channel moving heads) and **not**
> for profiles like the one in-repo.

Confirmed in the current tree: `grep -rn "shutter_channel" tests packages` returns
exactly one test-side assignment, `tests/unit/config/test_fixtures.py:399`
(`shutter_channel=17`). There is no tracked *rig config file* at all.

**Why the 4-head rig is the reference.** From `reviews/phases/interfaces-and-engineering.md`
(P7-M1, CONFIRMED):

> `main.py:208` passes a literal `fixture_count=4` into `build_moving_heads_pipeline(...)`,
> which flows into the planner prompt path (`stage.py:145` → `orchestrator.py:75`) —
> while the user's *actual* fixture config is resolved three lines later
> (`main.py:214-217`, `_resolve_fixture_config_path`) and never reconciled against the
> literal. On the only shipped path, any rig that does not have exactly 4 fixtures gets
> a planner that is told a false count.

Confirmed present: `packages/twinklr/cli/main.py:93` and `:208` both contain
`fixture_count=4`; `:211` contains `min_pass_score=7.0`;
`_resolve_fixture_config_path` is at `:50`. P1P-T11 removes those hardcodes — the 8-head
rig delivered here is what proves the removal works.

**Chase-ordering caveat that the 8-head rig will exercise** (P4-F26, verbatim):

> `_order_fixtures_for_chase` (`template_compiler.py:227`) hard-codes an 11-element role
> order and a fixed centre index of 5 … Acceptable for the 4-head reference rig; fragile
> beyond it.

**Template census facts the plan fixture must respect** (re-derived by AST against the
current tree during spec authoring, matching the `[V]` corrected census):
**37 templates; `cycle_bars` = 4.0 ×34, 8.0 ×1 (`ambient_random_wash`), 2.0 ×2
(`ballyhoo_chaos`, `build_drop_recover`)**.

Relevant symbols (verified present):
- `packages/twinklr/core/config/fixtures/dmx.py` — `DmxChannelMapping`, `ShutterMap`
  (`closed=0` `:16`, `open=255` `:17`), `shutter_default=255` "usually open" (`:94-95`).
- `packages/twinklr/core/config/adapter.py` — `get_max_channel` (`:77`).
- `packages/twinklr/core/agents/sequencer/moving_heads/models.py` — `PlanSection`,
  `ChoreographyPlan`.
- `packages/twinklr/core/sequencer/timing/beat_grid.py` — `BeatGrid`.

## Current behavior

- No fixture rig configuration is tracked in the repository; the CLI resolves a user
  path (`_resolve_fixture_config_path`) that only exists on the author's machine.
- No deterministic `ChoreographyPlan` fixture exists; every plan in tests is either an
  ad-hoc inline construction or a `MagicMock`.
- Consequently, a render cannot be reproduced by a second person or by CI.

## Target behavior

Three tracked rig configs plus one plan fixture, all under version control, all
consumable by the P1P-T1 harness:

| Rig | Fixtures | Purpose |
|---|---|---|
| `rig_4head_reference` | 4 | Matches the author's rig and the CLI's hardcoded `fixture_count=4`; the primary golden target |
| `rig_8head` | 8 | Proves the pipeline is not 4-specific; exercises `_order_fixtures_for_chase` beyond the reference rig; the acceptance rig for P1P-T11's hardcode removal |
| `rig_shutter_high` | 4 | Identical to the reference rig except `shutter_channel=17` (>16), for the two-arm shutter test in P1P-T1 |

The reference rig maps shutter **inside** 1–16 (use `shutter_channel=6`, matching the
P4-F3 test spec) so the "actively zeroed" arm is real.

Plan fixture: a `ChoreographyPlan` of **4 sections** covering, at minimum, one section
whose bar count is an exact multiple of `cycle_bars`, one whose bar count leaves a
remainder, one **1-bar section** (renders nothing today — P4-F4), and one section naming
a narrative multi-step template (`build_drop_recover` or `intro_main_outro_phrase` —
renders only its middle step today, P4-F5). Include a fixed `BeatGrid` with
**non-uniform** bar boundaries and a **non-zero first downbeat** so the P1P-T4 grid fix
is observable.

**Non-goals.** No audio file, no analyzer run, no LLM call, no plan *generation*. Do not
"fix" the plan to avoid the defect-triggering sections — the fixture's job is to
*expose* them.

## Implementation approach

Files to create (paths are a recommendation; keep them together and consistent with
whatever P1P-T1 chose):
- `tests/fixtures/rigs/rig_4head_reference.json`
- `tests/fixtures/rigs/rig_8head.json`
- `tests/fixtures/rigs/rig_shutter_high.json`
- `tests/fixtures/plans/deterministic_plan.json` (+ a loader helper returning a
  validated `ChoreographyPlan`)
- `tests/fixtures/beat_grid.json` (or a factory function producing the fixed grid)
- A `conftest.py` exposing `rig_config(name)`, `deterministic_plan()`, and
  `fixed_beat_grid()` fixtures.

Design decisions already made (do not relitigate):
- Rig configs are **data files in the real production schema** (loaded through the same
  loader the CLI uses), not Python objects hand-built in tests — otherwise they cannot
  serve as the CLI input P1P-T11 introduces.
- The shutter-high rig differs from the reference rig **in exactly one field**, so the
  golden diff between the two isolates the shutter behavior.
- The `BeatGrid` fixture is hand-authored with an explicitly non-uniform tempo, because
  a uniform grid would make Grid A and Grid B agree and hide P4-F2.

Sequencing constraints that apply (copied verbatim from `changes/twinklr-reactivation-review/build/plan/00-overview.md`):

> **Verification currency**: evidence in specs is from baseline `aa8d325`. Executors
> must re-verify cited line numbers before editing (the tree will drift as phases land)
> — specs cite symbol + file, with line numbers as hints only.

> `make validate` equivalents (check-only forms until P0-T4 lands the guard) must pass
> at every merge; golden tests (once P1P-T1 exists) must pass for any lane touching
> render/export code.

Coordination note from the phase plan: *"Lane G (golden first): T1 → T2 (harness before
any render change; everything in Lane R diffs against it)."* Also coordinate the file
location with P0-T2's `requires_template_data` fixture decision so there is one home for
tracked test data, not two.

## Acceptance criteria

- [ ] All three rig configs load through the production fixture-config loader (the same
      code path `_resolve_fixture_config_path` feeds) with no test-only shims.
- [ ] `rig_4head_reference` and `rig_shutter_high` differ **only** in the shutter channel
      value — verifiable by a diff of the two files that shows exactly one changed line.
- [ ] `rig_4head_reference` declares a shutter channel ≤ 16 (recommended: 6) and
      `rig_shutter_high` declares 17.
- [ ] At least one rig declares a **narrow tilt calibration** (e.g. `tilt_min_dmx=110`,
      `tilt_max_dmx=145`, the P4-F9 worked example) so the calibration-annihilation fix
      in P1P-T5 has a golden that moves.
- [ ] The plan fixture validates against today's `ChoreographyPlan` /`PlanSection`
      models with no `extra` fields, and contains the four section shapes listed above.
- [ ] The `BeatGrid` fixture has `bar_boundaries[0] != 0` and non-constant bar spacing;
      a test asserts both properties so a future "simplification" cannot silently make
      the grid uniform.
- [ ] The P1P-T1 golden suite runs green against all three rigs with no network access
      and no `OPENAI_API_KEY` set.
- [ ] Total added fixture data is small enough to review by eye (target: under ~300 lines
      across all files).

**Golden-diff expectation (BEFORE/AFTER):**

```
BEFORE: golden suite has no rigs to parameterize over; only the reference-rig
        placeholder from P1P-T1 exists.
AFTER : goldens exist for all three rigs. Expected baseline content differences:
          rig_4head_reference  → contains "E_SLIDER_DMX6=0"
          rig_shutter_high     → contains no "E_SLIDER_DMX17" token
          rig_8head            → 8 fixtures' worth of effects; chase ordering
                                 clusters unmapped roles (P4-F26, recorded not fixed)
        The 1-bar section produces ZERO effects in every rig's golden (P4-F4),
        and the narrative template produces only its middle step (P4-F5).
        Both are recorded as baseline, not fixed here.
```

## Tests

| Test | Behavior pinned |
|---|---|
| `test_rig_configs_load_via_production_loader[rig]` | Configs are valid production input, not test-only structures |
| `test_reference_and_shutter_high_differ_only_in_shutter_channel` | The two-arm shutter test is a controlled comparison |
| `test_deterministic_plan_validates_against_current_models` | Fixture cannot drift from `PlanSection` silently |
| `test_beat_grid_fixture_is_non_uniform_and_offset` | The grid fixture keeps the property that makes P4-F2 visible |
| `test_plan_fixture_contains_short_and_narrative_sections` | The defect-exposing section shapes cannot be quietly removed |

## Verification commands

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy .

uv run pytest tests/fixtures -v                # fixture self-tests
uv run pytest tests/golden -v                  # harness green across all three rigs

# offline/no-key proof
env -u OPENAI_API_KEY uv run pytest tests/golden -q
```

No LOCAL-ONLY steps. No paid API calls.

## Effort & risk

**Effort: S.**

Main risk: **inventing a fixture-config schema that production does not accept**, which
would make the rigs useless as the CLI input P1P-T11 needs. Mitigation: build each rig
by round-tripping through the real loader in a test (acceptance criterion 1) before
committing, and derive field names from
`packages/twinklr/core/config/fixtures/dmx.py` rather than from documentation.

Secondary risk: the 8-head rig triggers an outright exception in
`_order_fixtures_for_chase` rather than merely degraded ordering. If it does, record the
traceback in the task's handoff and mark it as evidence for P1P-T5's scope — **do not
fix it in this task** (Lane G must not change render behavior).
