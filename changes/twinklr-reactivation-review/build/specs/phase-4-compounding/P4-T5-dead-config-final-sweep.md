# P4-T5 — Dead-config final sweep

Phase: 4-compounding · Lane: config-sweep (touches `config/models.py`,
`config/loader.py`, every call site that reads or fails to read a config field, plus
a new generated test module — see Implementation approach) · Executor: sonnet ·
Verifier: opus · Depends on: P1P/P2P/P3 wiring done (per
`changes/twinklr-reactivation-review/build/plan/07-phase-4-compounding.md` task table)

## Objective

Resolve every remaining CC-1 dead-configuration member to exactly one of three states —
**wired-with-a-behavior-test**, **fixed-policy-with-an-invariant-test**, or
**deleted-with-a-P4-T6 documentation disposition** — and ship a
generated knob-inventory test that walks every declared config field and fails CI if
that field has neither a registered observable-effect test nor a registered removal
record. This test is the phase's real deliverable: it turns "dead config" from a
one-time cleanup into a class of bug that cannot silently reoccur.

## Evidence & background

**CC-1** (`findings.md:35`): "Dead-configuration class (~20 members incl. token
budget ×3 paths, `judge_agent`, inert `success_threshold`, crashing
`max_iterations=0`, checkpoint, logging, `cancel_token`, channel/fixture fields,
template defaults, CLI hardcodes over live config) — user guide unreliable as
behavior description." Sources: `P7-M2, P1-F5..F8/F10/F15/F19, P3-F2/F6/M-A/M-B,
P4-F15/F16/M1, P2-M11/M14`.

**Why "final sweep":** this task runs after P1P/P2P/P3 have already wired or removed
whatever CC-1 members those phases' own tasks touched incidentally (e.g., a phase
fixing the intensity-overwrite bug may also have wired a related channel field).
This task's job is to (a) re-audit the CC-1 list against the current tree — some
members may already be resolved, don't re-fix them — and (b) close out every member
still in the dead/documented-but-inert state, with the generated test as the
permanent backstop.

### Known CC-1 members (re-verify each against the current tree before acting —
this list is baseline `aa8d325` evidence; some entries may already be closed by
earlier phases)

| Member | Evidence | Current disposition per finding |
|---|---|---|
| `IterationConfig.token_budget`, `AgentOrchestrationConfig.{token_budget,enforce_token_budget}`, `AgentSpec.token_budget` (3 independent surfaces) | P3-F6, `llm-agents-and-planning.md:921-932`: only #1 is functional (fed nowhere); #2 read only by the dead `TokenBudgetManager`; #3 threaded from all four orchestrators into every spec factory but "grep-verified never read by `async_runner.py`" | "keep exactly one and delete the other two" |
| `AgentOrchestrationConfig.judge_agent` | P3-F2, `llm-agents-and-planning.md:873-884`: zero readers anywhere; macro judge silently defaults to `gpt-5.2` via `macro_planner/specs.py:44`; MH judge independently defaults to `gpt-5-mini` (`moving_heads/specs.py:46`) — NOT affected, correction to an earlier overstatement | FIX (wire `judge_agent` into `MacroPlannerOrchestrator`) |
| `JudgeVerdict.enforce_status_matches_score` / `success_threshold` | P3-M-A (per `findings.md` CC-1 sources; cross-ref `verification.md` Phase-3 section): hardcodes 7.0/5.0, controller compares status only — the knob is fully inert | FIX (thread the configured threshold through) or REMOVE (delete the knob, document the hardcoded behavior) |
| `AgentOrchestrationConfig`/`IterationConfig` `max_iterations=0` | P3-M-B (`verification.md` Phase-3 section): documented as "skip judge," passes `AgentOrchestrationConfig`'s `ge=0` validator then CRASHES `IterationConfig`'s `ge=1` validator — an actively failing documented value, not merely inert | FIX (make `max_iterations=0` actually work, since it's documented) — this is the one CC-1 member that is actively broken, not just silently ignored; treat with priority |
| `JobConfig.checkpoint`, `PipelineContext.checkpoint_dir` | P1-F7, `foundation-and-orchestration.md:973-978`: no readers in `packages/`; the only checkpoint-shaped code (`reporting/evaluation/collect.py:16-71`) reads a format nothing produces | REMOVE, or wire once the eval-writer restoration (SF-4, tracked in a Phase 1P/3 task, verify it hasn't already resolved this) exists |
| `StageDefinition.critical` | P1-F5, `foundation-and-orchestration.md:955-963`: documented as controlling lyrics-stage optionality; self-described as "Legacy field (reserved)"; executor terminates on any failure regardless; a test pins the current (contradictory) behavior (`tests/unit/pipeline/test_pipeline.py:311`) | FIX (implement optionality) or REMOVE (delete the field, correct the docstring, update the pinning test) |
| `PipelineDefinition.fail_fast` | P1-F6, `foundation-and-orchestration.md:966-971`: read only by a debug log; termination unconditional; both definitions set it `True` | REMOVE |
| `StageDefinition.retry_config`/`timeout_ms` on FAN_OUT stages | P1-F8, `foundation-and-orchestration.md:981-987`: `_execute_fan_out` returns before the retry/timeout block runs; the one FAN_OUT stage (LLM group planner) is exactly where transient errors are most likely | FIX (make FAN_OUT honor these fields). P4-T4 explicitly preserved this generic pipeline policy; it is not an LLM transport-retry duplicate. |
| `cancel_token` | P1-F10, `foundation-and-orchestration.md:997-`: never assigned in production; executor's check is dead code | IMPLEMENT-OR-DELETE |
| `AgentConfig.{temperature,max_tokens,timeout_seconds}` for `plan_agent`/`implementation_agent`/`refinement_agent`; MH/group judge and planner models | P1-F15, `foundation-and-orchestration.md:1063-1085`: only `plan_agent.model` is read anywhere in live code; MH planner model comes from a Python default (`moving_heads/specs.py:14`), not config; judges likewise; `temperature`/`max_tokens`/`timeout_seconds` unwired everywhere including for the one configured field | FIX (wire the moving-heads/group planner and judge models to config; wire `temperature`/`max_tokens`/`timeout_seconds` or delete them) — **NOTE**: model-ID wiring itself may already be done by Phase 2P's model retarget (M1); re-verify before re-doing that part — this task's residual scope is likely just `temperature`/`max_tokens`/`timeout_seconds` |
| `AppConfig.llm_api_key` empty-string default | P1-F19, `foundation-and-orchestration.md:1141-1146`: defaults to `SecretStr(os.getenv("OPENAI_API_KEY", ""))`, nothing validates non-emptiness outside the CLI's own separate gate; scripts/tests get a late 401 instead of a fast failure | FIX (validate non-emptiness at config-construction time, not just in the CLI) |
| `dimmer_floor_dmx` template default (and 9 other template step-timing fields) | P4-M1 (movement-heads-rendering.md, cited in `findings.md` CF-6/P4-F15 family) + P4-F15 (`moving-heads-rendering.md:1047-1063`): `Template.defaults` never read — all 37 templates' `dimmer_floor_dmx=60` silently dropped, dimmers drive to 0; separately, `mode`, `quantize_type`, `start_offset_bars` are declared on every template but the compiler reads only `duration_bars` — "phase 4 contributes three more members to [the dead-configuration] class" | FIX (P4-M1's dimmer-floor drop has an OUTPUT consequence — this specific member should already be prioritized by whatever task fixes the render-output-changing defects per the phase-4 deletion order §1-2; re-verify it isn't already fixed before duplicating work here) or REMOVE (delete the timing fields if genuinely unwanted) |
| `channel_defaults.{shutter,color,gobo}` | P4-F16 family / P7-M2 (`verification.md` P7-M2 block): documented in `docs/user-guide.md:152-154` as live; zero readers | REMOVE + doc correction (coordinate with P4-T6) |
| Five network-feature `enable_*` flags vs. env-var docstrings | P2-M11, `deterministic-audio-analysis.md:687`: `config/models.py:234-249` `enable_*` flags default `False`; `AppConfig` has no environment-variable binding (`ConfigDict(extra="ignore")`, not `BaseSettings`) despite docstrings (`:309,313`) instructing users to set env vars — setting `ACOUSTID_API_KEY`/`GENIUS_ACCESS_TOKEN` alone produces no behavior change | FIX (bind to env vars, or correct docstrings to state the `config.json` flag is also required) |
| `SectioningPreset.context_weights` | P2-F9 (`deterministic-audio-analysis.md:660`): populated/validated for all 11 genre presets, zero downstream readers | REMOVE, or wire in |
| `energy/profiling.py`'s per-genre `gradient_percentile` | P2-M14 (`deterministic-audio-analysis.md:690`): defined for 6+ genre profiles, only ever read for a debug log string, never in a threshold computation (unlike its sibling `drop_gradient_percentile`, which IS load-bearing) | REMOVE, or wire in |
| `config/models.py:326-335`'s six HTTP-resilience fields | P1-F13 (`foundation-and-orchestration.md`, adjacent finding, same class): `http_max_retries`, `http_timeout_s`, `http_circuit_breaker_threshold`, `http_circuit_breaker_timeout_s`, `musicbrainz_rate_limit_rps`, `musicbrainz_timeout_s` — none of the six was read; no circuit breaker exists at all | Resolved by P4-T4: retry count, HTTP timeout, MusicBrainz rate, and MusicBrainz timeout are wired with effect tests; the two circuit-breaker fields are deleted. P4-T5 must inventory the resulting live fields, not duplicate the implementation. |

**The user-guide angle (P7-M2, `verification.md` Phase-7 section):** every one of
these members that is documented in `docs/user-guide.md` as live is part of the class
verification.md calls out by name: "`token_budget` (:146, no-op), `judge_agent.model`
(:148, never wired), `channel_defaults.{shutter,color,gobo}` (:152-154, zero
readers), `checkpoint` (:157, zero readers), a false resume promise (:296),
`logging.level` (:121, bypassed), and shutter/color/gobo curve claims (:245,
disproved). **Every one fails silently. The user guide is not a reliable behavior
description — confirmed as a CLASS.**" Doc corrections for whichever members this
task deletes (rather than wires) are P4-T6's job — hand off the final
deleted/wired list to that task rather than editing `docs/user-guide.md` here (avoid
cross-task file conflicts); if T6 has already landed when this task runs, coordinate
directly instead of leaving a dangling correction.

## Current behavior

Every member in the table above exists in the config schema, is either documented as
live (in `docs/user-guide.md` and/or field docstrings) or silently accepted, and has
zero or broken behavioral effect. No mechanism exists to detect a NEW dead-config
member being introduced in the future — CC-1 was found by manual grep-based review,
not by an automated check.

## Target behavior

- Every field under the explicitly enumerated external Pydantic roots `AppConfig`,
  `JobConfig`, `FixtureGroup`, and `TemplateDoc` is in exactly one of three states:
  **wired** (a test proves changing the field's value changes observable program
  behavior), **invariant** (a test proves the fixed policy literal and rejects
  alternatives), or **removed** (the field no longer exists, and if it was
  documented, the doc is corrected — coordinate with P4-T6).
- A generated test (see Implementation approach) enumerates every currently-declared
  config field and fails if a field has neither a registered effect-test reference
  nor a registered removal record. This test runs in CI as part of `make validate`
  going forward.

**Non-goals:** re-doing wiring already completed by P1P/P2P/P3 tasks (re-verify, don't
duplicate). Resolving the six HTTP-resilience fields if P4-T4 already claims them
(coordinate, don't fork the decision). Editing `docs/user-guide.md` directly — hand
the final wired/removed list to P4-T6.

## Implementation approach

**The knob-inventory test mechanism (this task's core deliverable):**

1. **Enumeration**: write a helper that recursively walks the explicit external
   roots `AppConfig`, `JobConfig`, `FixtureGroup`, and `TemplateDoc` using
   `model_fields` introspection over nested and union models, and produces canonical
   full paths. Repeated roles and fixture alternatives remain distinct paths. This
   is the accounted external surface — it must be driven by the Pydantic schema
   itself (source of truth), not a hand-maintained list that can drift from the
   schema the way `docs/user-guide.md` drifted from the code.
2. **Registry**: a single file (e.g.
   `tests/config_effects_registry.py` or a YAML/TOML sidecar — executor's choice,
   but it must be a single source checked into the tree, not scattered
   annotations) mapping each canonical full path to one of:
   - `EFFECT_TEST = "tests.path.to.test_function_name"` — a pointer to an existing
     test that sets the field to a non-default value and asserts an observable
     difference (log line, emitted DMX byte, API request body shape, cache-key
     content, exception raised, etc. — whatever "observable effect" means for that
     field).
   - `INVARIANT_TEST = "tests.path.to.test_function_name"` — a pointer to an
     existing test proving a fixed policy literal and rejection of alternatives.
   - `REMOVED = "<task-id>, <date>, <one-line reason>"` — for fields deleted before
     this test existed, or fields this task itself removes (in which case the field
     also physically no longer exists in `config/models.py`, so it drops out of the
     enumeration — the `REMOVED` record type is for historical/audit purposes in the
     registry, or, simpler: once a field is deleted, remove its registry entry too
     and let the enumeration's absence be the record; pick whichever the executor
     finds cleaner, document the choice).
3. **The generated test**: a single parametrized pytest test
   (`test_every_config_field_has_a_registered_effect` or similar) that iterates the
   enumeration from step 1 and asserts each canonical full path has a
   registry entry from step 2. This test does NOT re-run every effect test itself
   (that would just be "run the test suite") — its job is **completeness**: every
   live field has *some* accountable record, every referenced pytest nodeid really
   collects, and every removal is absent with a P4-T6 disposition. A newly-added
   config field with no effect/invariant test and no removal record fails CI by
   name, rather than
   accumulating silently the way CC-1's ~20 members did.
4. **Populate the registry** for every currently-live field using this task's own
   wiring work (each field this task wires gets a real effect test written and
   registered; each field this task removes drops out of the enumeration) plus, for
   any field ALREADY correctly wired by earlier phases, a lightweight registry entry
   pointing at whatever test already covers it (write one if none exists — a wired
   field with no test is itself a gap this task should close).

**Sequencing within this task**: resolve the config-fields table above first (each
member: wire-with-test or remove-with-doc-note), THEN build the generated test last,
once the registry has something real to populate — building the test first against
an empty/incomplete registry just produces a big red list with no context.

## Acceptance criteria

- No config field under the four explicit external roots remains in a state where it
  is documented or silently present but has zero/broken behavioral effect — for
  every member in the table above (and any additional ones the enumeration surfaces
  that weren't in the review's original ~20), the state is wired-with-test or
  removed-with-doc-note.
- `max_iterations=0`'s crash (P3-M-B) specifically no longer crashes and behaves as
  documented ("skip judge"), OR the documented value is corrected to state it is
  invalid and a `ge=1` validation error is the intended, tested behavior — pick one,
  don't leave the crash unaddressed (it's the one CC-1 member that's actively
  broken, not just inert).
- The generated knob-inventory test exists, runs under `make validate`, and fails
  with a clear per-field message when a config field lacks a registry entry (prove
  this by temporarily adding an unregistered dummy field in a throwaway commit
  during development — not part of the final diff — and confirming the test fails
  named at that field; remove the dummy field before finalizing).
- `make validate` passes with the new test included.

## Tests

- One effect-test per wired field (see registry mechanism above) — each is a
  small, focused test: set the field to a non-default value, assert the specific
  observable consequence.
- The generated completeness test itself (`test_every_config_field_has_a_registered_effect`
  or equivalent name).
- `max_iterations=0` gets an explicit test pinning its corrected (non-crashing, or
  intentionally-invalid-and-validated) behavior.

## Verification commands

```bash
uv run pytest tests/ -v -k "config_effect or knob_inventory or config_field"
uv run pytest tests/ -v
uv run mypy .
uv run ruff check .
```

## Effort & risk

**L.** Main risk: scope creep — CC-1 has ~20 members spanning five phases' worth of
subsystems (pipeline execution, LLM agents, moving-heads templates, audio analysis,
HTTP resilience), and several overlap other Phase-4 tasks' file lists (P4-T4's retry
fields, P4-T3's already-deleted diarization config, P4-T6's doc corrections).
Mitigation: the per-member table above states known overlaps explicitly and
instructs re-verification/coordination rather than blind re-fixing; the generated
test is scoped to *completeness of accounting*, not to re-implementing every wiring
decision from scratch inside this one task.

## Execution record (2026-08-26)

The implemented inventory deliberately narrows and makes explicit the external
configuration roots that this task can prove: `AppConfig`, `JobConfig`,
`FixtureGroup`, and `TemplateDoc`. It walks their complete recursive Pydantic
schemas and records canonical full paths, including distinct repeated agent roles
and fixture alternatives. This replaces the original `(model_name, field_name)`
proposal, which could incorrectly allow one role's evidence to bless another.

The checked-in registry has three dispositions:

- `EFFECT_TEST`: a real, collectable pytest node proving observable behavior;
- `INVARIANT_TEST`: a real, collectable pytest node proving a fixed policy literal;
- `REMOVED`: an absent schema path with the disposition that P4-T6 must remove any
  stale published documentation.

The inventory test checks exact schema/registry equality, validates removal
absence and disposition, and uses pytest collection to reject invented nodeids.
P4-T6 should consume the registry's `REMOVED` records rather than maintain a
second deletion list.

This task removed only the verified-zero-consumer App/Job/audio, fixture, and
template fields recorded as `REMOVED` in the registry. Representative old
configuration for those paths fails loudly with targeted migration messages.
Live relative DMX mappings, inversions, calibration, fixture names/groups,
position offsets, movement safety, template phase mode/spread/wrap/order and aim
zone, timeline section gating, timing offset, and fixed policy literals have
behavioral or invariant evidence.

`PhaseOffset.order` was initially classified as dead, but compiler inspection and
a red-first output discriminator proved it changes per-fixture schedules. It was
restored and registered as live evidence. This correction is retained here to
prevent future grep-only reclassification.

Generic pipeline `FAN_OUT` items now use the same stage retry/timeout policy as
sequential stages, with public behavioral discriminators for both knobs. Provider
retry/logging/HTTP configuration remains P4-T4-owned. After approved P4-T4
integration, this registry consumes its observable CLI logging and HTTP
retry/timeout evidence and records its two circuit-breaker deletions. The remaining
`job.agent.llm_logging.sanitize` forwarding gap was fixed red-first in P4-T5.

The first post-P4-T4 candidate, `607bf19`, is preserved as rejected evidence. Its
registry used generic smoke/fingerprint pointers, collapsed fixture union alternatives,
allowed representative removed App/Job keys to be silently ignored, and overstated its
handoff evidence. None of that candidate's passing counts constitutes acceptance.

The remediated implementation type-qualifies union alternatives, validates every pytest
node ID by collection, and gives each live canonical path an exact non-default mutation
at a shipped seam. App/Job migration validators reject only the specifically removed
keys, preserving unrelated forward-compatible extras. Confirmed-zero-reader App/Job,
audio, fixture, and template leaves are absent from schema and retained as `REMOVED`
ledger entries for P4-T6; fixed literals use `INVARIANT_TEST` rather than fabricated
effects. Fresh focused evidence is 106 inventory/collection tests plus the behavioral
matrix (all passing); Ruff and formatting are clean; mypy reports no issues in 719
source files. The final frozen commit identity and fresh full `make validate` evidence
belong in the task handoff after the gate completes; this specification does not
self-approve the candidate.

### Verifier rejection and remediation

The subsequent frozen candidate `a2fe16e` is also preserved as rejected evidence.
It incorrectly classified four live behavior clusters as removable based on an
incomplete consumer audit:

- `FixturePosition.pan_offset_deg` / `tilt_offset_deg` and the public
  `apply_offset` / `remove_offset` conversions;
- `MovementLimits.avoid_backward` and public `FixtureConfig.is_pose_safe` safety
  behavior, through both base-config and fixture-instance schema paths;
- `TimelineTracksConfig.sections`, which gates section emission when the public
  timeline builder receives section data; and
- `Geometry.aim_zone`, which is forwarded into compiled geometry parameters and
  emitted segment metadata.

The remediation restored those schema fields and public seams, removed their
false `REMOVED` and migration-rejection records, and registered exact
path-specific `EFFECT_TEST` node IDs. Red-first discriminators covered both
fixture alternatives for each position offset, both configuration sources for
backward safety, enabled and disabled timeline section emission, and two
non-default aim zones reaching compiled metadata. The replacement candidate
still requires fresh full gates and independent verification; this execution
record does not approve it.
