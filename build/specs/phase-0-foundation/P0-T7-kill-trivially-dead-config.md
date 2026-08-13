# P0-T7 — Kill the trivially-dead config

Phase: 0-foundation · Lane: C (onboarding/docs, independent of Lane A after T1) ·
Executor: sonnet · Verifier: opus · Depends on: P0-T4 (CI protects this change)

## Objective

Delete (not wire) the config/code surfaces already adjudicated dead-with-no-future-intent
by the review: the `TokenBudgetManager` class, the `OrchestrationStateMachine` module,
`pipeline/stages.py`, the `checkpoint`/`checkpoint_dir` fields (superseded by a future
checkpoint-writer task, P1P-T10, not this task), and the inert `critical`/`fail_fast`/
`PARALLEL`/`CONDITIONAL`-redundancy in the pipeline executor. This task **removes**
capability, it does not implement any of it — that is explicitly out of scope here.

## Evidence & background

- **Findings CC-1 (subset), P1-M4, P1 §6** (`changes/twinklr-reactivation-review/reviews/findings.md`):
  CC-1 "Dead-configuration class (~20 members incl. token budget ×3 paths, judge_agent,
  inert success_threshold, crashing max_iterations=0, checkpoint, logging, cancel_token,
  channel/fixture fields, template defaults, CLI hardcodes over live config)" —
  disposition "FIX or REMOVE per member → RM-1.5, RM-5.2." This task handles the REMOVE
  subset only (see "do NOT touch" list below for the FIX-elsewhere subset).
- **`reviews/phases/foundation-and-orchestration.md` §4.1** ("The declarative DAG: three
  of its knobs do not work"): "`PipelineDefinition.fail_fast` is likewise inert: read
  only by a debug log (`executor.py:85`), while termination is unconditional
  (`executor.py:141-151`). So is `cancel_token` — the executor's check is real code
  guarding a field nothing ever sets (P1-F10). **Five declared controls are inert in
  total**: `critical`, `fail_fast`, `cancel_token`, `checkpoint`/`checkpoint_dir`, and
  two of the four `ExecutionPattern` members [`PARALLEL`, `CONDITIONAL`]. They form one
  remediation bucket: implement or delete, but stop advertising." (`cancel_token` is
  explicitly **excluded** from this task — see scope note below; it is a candidate for a
  future implement-or-delete decision but this task's plan-table scope names only
  `critical`/`fail_fast`/`PARALLEL`/`CONDITIONAL`-redundancy, not `cancel_token`.)
- **Re-verified directly against the current tree** (this spec, baseline `aa8d325`):

  **`TokenBudgetManager`** — `packages/twinklr/core/agents/token_budget_manager.py`
  (274 lines). Confirmed **zero consumers anywhere**: `grep -rln
  "token_budget_manager\|TokenBudgetManager" packages/ tests/ scripts/` returns only the
  file itself. It is not even re-exported from `agents/__init__.py` (confirmed by
  reading that file's imports/`__all__` in full — no `TokenBudgetManager` reference
  anywhere in it). No dedicated test file exists (`find tests -iname
  "*token_budget*"` → no results). Fully dead: no importer, no export, no test.

  **`OrchestrationStateMachine`** — `packages/twinklr/core/agents/state_machine.py`
  (414 lines, 5 top-level symbols: `OrchestrationState`, `StateTransition`,
  `StateMetrics`, `InvalidTransitionError`, `OrchestrationStateMachine`). Confirmed:
  re-exported from `agents/__init__.py:48-54,67-71` (all five symbols), and consumed
  **only** by its own dedicated test file, `tests/unit/agents/test_state_machine.py`
  (21 tests). `grep -rn "from twinklr.core.agents import.*State\|agents.state_machine"`
  across `packages/`, `tests/`, `scripts/` (excluding the module's own file, its
  `__init__.py` export, and its own test file) → **zero hits**. The entire module is a
  self-contained, fully-typed, fully-tested dead feature — no production code path ever
  constructs or references an `OrchestrationStateMachine`.

  **`pipeline/stages.py`** — 253 lines. Confirmed **zero importers repo-wide**:
  `grep -rn "from twinklr.core.pipeline import stages\|from twinklr.core.pipeline.stages
  import\|import twinklr.core.pipeline.stages" packages/ tests/ scripts/` → zero hits.
  The file's own docstring (line 1-5) frames itself as reference/example code: "Example
  pipeline stages for Twinklr sequencer. Demonstrates how to wrap existing components as
  pipeline stages. These are reference implementations - adapt as needed." Line 252
  carries a dangling reference: `# See changes/archive/group_planner_v3_failed/
  ARCHIVE_NOTES.md for details.` — `changes/archive/group_planner_v3_failed/` does not
  exist in the current tree (confirmed: `ls changes/archive/group_planner_v3_failed`
  → no such file or directory), corroborating this is leftover, orphaned reference code
  from an abandoned migration, not live product code.

  **`checkpoint_dir` / `checkpoint` fields.** `PipelineContext.checkpoint_dir`
  (`pipeline/context.py:61`, declared `Path | None = None`, documented at line 33)
  confirmed **zero production readers**: `grep -rn "checkpoint_dir" packages/ tests/
  scripts/` returns only the field's own declaration/docstring in `context.py` and a
  single test fixture (`tests/unit/audio/conftest.py:209`,
  `config.checkpoint_dir = "/tmp/test_checkpoints"`) that sets it on an unrelated
  `config` object and is never asserted against — i.e., nothing reads this field
  anywhere in application code. `JobConfig.checkpoint` (`config/models.py:521`,
  `checkpoint: bool = True`) likewise confirmed zero production readers — the only hit
  outside its own declaration is `tests/integration/audio/test_lyrics_analyzer_integration.py:33`
  (`config.checkpoint = False`), a test-only set with no corresponding read anywhere.
  This matches the corpus-intelligence phase review's independent confirmation
  (`reviews/phases/corpus-intelligence.md` P6-F3): "`JobConfig.checkpoint` (zero readers)
  named as 4th dead-config member in this scope" — cited there as one of the fields a
  **future, real** checkpoint writer (P1P-T10, out of this task's scope — see the
  sequencing note below) would give meaning to. This task deletes the fields as
  currently-dead; P1P-T10 is responsible for reintroducing checkpoint support with a
  real writer if/when it lands, not this task.

  **`critical` field** (`pipeline/definition.py:70,119`): declared `critical: bool =
  True` on `StageDefinition`, documented in its own docstring as "Legacy field
  (reserved). Pipeline execution is fail-fast on stage failure." Confirmed inert by the
  phase-1 review and independently re-confirmed here: no code path reads
  `StageDefinition.critical` to alter execution behavior (only the docstring text
  claims fail-fast is unconditional, matching `executor.py:141-151`'s actual
  unconditional termination). `definitions/common.py:29-30,68` still sets
  `critical=False` on the `lyrics` stage — a value that is read by nothing. The
  phase-1 review's test-evidence note applies here too: `tests/unit/pipeline/
  test_pipeline.py:311` (`test_fan_out_any_failure_fails_stage_even_when_non_critical`)
  *pins* the fact that `critical=False` is ignored — i.e., the executor's behavior
  (ignore `critical`) is itself tested and intentional; it is the field and its
  callers that are the stale part.

  **`fail_fast` field** (`pipeline/definition.py:163,183`): declared
  `fail_fast: bool = Field(default=True, description="Stop on first failure")` on
  `PipelineDefinition`. Confirmed read in exactly one place, a debug log statement
  (`executor.py:85`, `f"  Fail fast: {pipeline.fail_fast}"`) — never consulted to alter
  control flow; termination on first wave failure is unconditional
  (`executor.py:141-151`, confirmed by direct read).

  **`ExecutionPattern.PARALLEL`/`ExecutionPattern.CONDITIONAL`**: confirmed via
  `grep -rn "ExecutionPattern.PARALLEL\|ExecutionPattern.CONDITIONAL\|pattern=ExecutionPattern"
  packages/twinklr/core/` — `PARALLEL` appears **only** in a docstring example
  (`definition.py:88`) and the `pipeline/README.md` narrative doc; it is **never set on
  any real `StageDefinition` anywhere in `packages/` or `scripts/`** (parallelism is
  derived purely from the dependency graph regardless of this field —
  `executor.py:238-242`). `CONDITIONAL` is set exactly once, redundantly
  (`definitions/common.py:66`, on the `lyrics` stage, which also carries a real
  `condition=` callable) — `should_execute()`
  (`definition.py:125-136`, re-verify exact range) runs for **any** stage carrying a
  `condition`, regardless of its declared `pattern`, so the `CONDITIONAL` value on that
  one call site does nothing beyond documentation.

## Notes for spec authors (from `build/plan/01-phase-0-foundation.md`, copied verbatim)

> T7 explicitly must NOT touch: `success_threshold`, `max_iterations`, `judge_agent`,
> channel/fixture defaults, `Template.defaults` — those get WIRED (not deleted) in
> P1P/P2P tasks.

This is a hard boundary for this task. Do not delete, rename, or otherwise modify
`AgentOrchestrationConfig.success_threshold`, `.max_iterations`, `.judge_agent`,
`ChannelDefaults`/any `channel_defaults`/fixture-default fields, or
`Template.defaults` (`config/models.py` and the templates/group model it lives on) —
even though several of these are *also* currently dead/inert per the phase-1 and
phase-4 reviews, they are explicitly reserved for **wiring**, not removal, in later
phases (P1P = Phase 1P render truth, P2P = Phase 2P creative quality — see
`build/plan/00-overview.md`'s program map). Deleting them here would directly conflict
with that later work. If in doubt whether a given dead-config member belongs to this
task's REMOVE list or the later-phases' WIRE list, check this exact do-NOT-touch list
first — it is exhaustive for what this task must leave alone.

Similarly, per this task's own plan-table row: "Larger dead-code retirement waits for
Phase 4 (sequencing traps)." This task's scope is deliberately narrow — the five items
named in the Objective, not a general dead-code sweep. Do not expand scope to other
findings' dead-code items (e.g. `CacheOptions`, the sync-wrapper layer, the three
logging subsystems documented in the phase-1 review §4.8) even though they are also
confirmed dead — those belong to Phase 4 per the plan's explicit sequencing note.

## Current behavior

- `TokenBudgetManager` (274 lines) and `OrchestrationStateMachine` + its four sibling
  symbols (414 lines) exist as fully-built, in some cases fully-tested, features with no
  production caller anywhere.
- `pipeline/stages.py` (253 lines) is orphaned reference code, unreachable from any real
  entry point, referencing a deleted archive directory.
- `PipelineContext.checkpoint_dir` and `JobConfig.checkpoint` are declared fields with
  zero production readers — a developer or config author who sets either gets no error
  and no effect.
- `StageDefinition.critical`, `PipelineDefinition.fail_fast`, and the
  `ExecutionPattern.PARALLEL`/`CONDITIONAL` enum members are declared, documented (in
  some cases with a misleading docstring example, per `definition.py:102-109`'s FAN_OUT
  + `retry_config` combination noted in the phase-1 review as itself broken — out of
  this task's scope to fix, only to note), and inert.

## Target behavior

- `TokenBudgetManager`'s file, and `OrchestrationStateMachine`'s file plus its
  `agents/__init__.py` export block and its dedicated test file, no longer exist.
- `pipeline/stages.py` no longer exists.
- `PipelineContext.checkpoint_dir` and `JobConfig.checkpoint` no longer exist as fields.
- `StageDefinition.critical` and `PipelineDefinition.fail_fast` no longer exist as
  fields; every current call site that sets them (`definitions/common.py:29-30,68`, and
  any others found during implementation) has that argument removed.
- `ExecutionPattern` no longer declares `PARALLEL`/`CONDITIONAL` members — only
  `SEQUENTIAL` and `FAN_OUT` remain (the two that are actually honored). The one real
  call site currently setting `pattern=ExecutionPattern.CONDITIONAL`
  (`definitions/common.py:66`) has that argument removed (the stage's `condition=`
  callable alone continues to gate execution, unchanged — `should_execute()`'s behavior
  does not depend on `pattern` today, so removing the enum member changes no runtime
  behavior).
- All docstrings/examples referencing any of the above (the class docstring examples in
  `definition.py:88,96`, `pipeline/README.md`'s narrative doc, `StageDefinition`'s own
  `critical` docstring line) are updated to stop advertising removed capability.
- The full test suite continues to pass at whatever pass rate P0-T2/T3 established,
  minus the deleted `test_state_machine.py`'s 21 tests (which test a deleted feature and
  are deleted with it) and any `test_pipeline.py` assertions that specifically pin the
  now-removed fields' inert behavior (e.g.
  `test_fan_out_any_failure_fails_stage_even_when_non_critical` — this test's *point*
  was to pin that `critical=False` is ignored; once the field is deleted, the test
  either needs deletion too, since there is nothing left to pin, or rewriting to assert
  the underlying always-fail-fast behavior without reference to the removed field —
  prefer the latter if the underlying behavior is worth keeping a regression test for,
  otherwise delete).

## Implementation approach

1. **Delete `packages/twinklr/core/agents/token_budget_manager.py`.** Confirm no
   importer via `grep -rn "token_budget_manager\|TokenBudgetManager"` before and after —
   should go from 1 file (itself) to 0.

2. **Delete `packages/twinklr/core/agents/state_machine.py`.** Remove its entire import
   block and `__all__` entries from `agents/__init__.py` (`__init__.py:48-54` import,
   `:67-71` `__all__` — re-verify exact line ranges before editing). Delete
   `tests/unit/agents/test_state_machine.py`.

3. **Delete `packages/twinklr/core/pipeline/stages.py`.** Confirm no importer (already
   verified zero repo-wide). Check whether any documentation (`pipeline/README.md`,
   `docs/`) references this file by name and remove/update those references too — a
   quick `grep -rn "pipeline/stages\|pipeline\.stages" docs/ packages/twinklr/core/pipeline/README.md`
   before finalizing.

4. **Remove `PipelineContext.checkpoint_dir`.** Delete the field
   (`pipeline/context.py:61`) and its docstring line (`:33`). Update the one test
   reference (`tests/unit/audio/conftest.py:209`) — since nothing reads this field, the
   fixture line can simply be deleted (confirm it isn't asserted against anywhere in the
   same test file before removing).

5. **Remove `JobConfig.checkpoint`.** Delete the field (`config/models.py:521`).
   Update the one test reference
   (`tests/integration/audio/test_lyrics_analyzer_integration.py:33`) similarly.
   **Do not** touch `docs/user-guide.md:157,296`'s checkpoint documentation as part of
   this task if P0-T6/P7-M2's config-reference-class fix is handling that doc
   separately — check whether that task has landed; if not, note the doc drift this
   creates (documenting a now-nonexistent field) but leave the doc fix to whichever task
   owns `docs/user-guide.md`'s config reference audit (P7-M2's disposition: "audit the
   full config table against live readers as one pass, not per-field patches" — this
   task is not that pass).

6. **Remove `StageDefinition.critical`.** Delete the field
   (`pipeline/definition.py:119`) and its docstring line (`:70`). Remove the
   `critical=False` argument from `definitions/common.py:68` (and any other call site
   found via `grep -rn "critical="  packages/twinklr/core/pipeline/`). Update or delete
   `tests/unit/pipeline/test_pipeline.py:311`'s
   `test_fan_out_any_failure_fails_stage_even_when_non_critical` per the Target
   behavior note above.

7. **Remove `PipelineDefinition.fail_fast`.** Delete the field
   (`pipeline/definition.py:183`) and its docstring line (`:163`). Remove the debug-log
   reference (`executor.py:85`) — either delete that log line or replace it with
   something that doesn't reference the removed field.

8. **Remove `ExecutionPattern.PARALLEL` and `ExecutionPattern.CONDITIONAL`.** Locate the
   `ExecutionPattern` enum definition (`pipeline/definition.py`, exact line not yet
   captured in this spec's evidence — re-verify via `grep -n "class ExecutionPattern"
   packages/twinklr/core/pipeline/definition.py` before editing) and remove the two
   members, leaving `SEQUENTIAL` and `FAN_OUT`. Update the docstring examples at
   `definition.py:88,96` (which currently demonstrate `PARALLEL`/`CONDITIONAL` usage) to
   either remove those examples or replace them with `SEQUENTIAL`/`FAN_OUT` equivalents.
   Remove `pattern=ExecutionPattern.CONDITIONAL` from
   `definitions/common.py:66` (the stage's `condition=` callable is untouched — it
   continues to gate execution exactly as before, since `should_execute()`'s behavior
   never depended on the `pattern` value). Update `pipeline/README.md`'s narrative
   examples (`:117,134` reference `FAN_OUT`/`CONDITIONAL` — remove the `CONDITIONAL`
   example, keep `FAN_OUT`).

9. **After each deletion, run the full test suite and mypy** before moving to the next
   item — these five deletions are independent of each other but each touches shared
   files (`pipeline/definition.py`, `pipeline/executor.py`,
   `pipeline/definitions/common.py`), so sequencing deletions one at a time with a
   test run between each catches any missed call site early rather than compounding
   errors across all five at once.

## Acceptance criteria

- `packages/twinklr/core/agents/token_budget_manager.py`,
  `packages/twinklr/core/agents/state_machine.py`,
  `packages/twinklr/core/pipeline/stages.py`, and
  `tests/unit/agents/test_state_machine.py` no longer exist.
- `agents/__init__.py` no longer imports or exports `OrchestrationState`,
  `OrchestrationStateMachine`, `StateTransition`, `StateMetrics`,
  `InvalidTransitionError`.
- `PipelineContext` has no `checkpoint_dir` field; `JobConfig` has no `checkpoint`
  field; `StageDefinition` has no `critical` field; `PipelineDefinition` has no
  `fail_fast` field; `ExecutionPattern` has exactly two members, `SEQUENTIAL` and
  `FAN_OUT`.
- `grep -rn "checkpoint_dir\|\.critical\b\|fail_fast\|ExecutionPattern.PARALLEL\|ExecutionPattern.CONDITIONAL\|TokenBudgetManager\|OrchestrationStateMachine\|pipeline\.stages\b"
  packages/ tests/ scripts/ docs/` returns zero hits (adjust the pattern to avoid
  false-positives on unrelated `.critical`/`checkpoint`-named things outside this task's
  scope — inspect each hit manually rather than trusting the grep blindly, since
  `critical` in particular is a common English word that may appear in comments/log
  messages unrelated to this field).
- `success_threshold`, `max_iterations`, `judge_agent`, `channel_defaults`/fixture
  defaults, and `Template.defaults` are byte-for-byte unmodified by this task's diff
  (verify with `git diff` scoped to `config/models.py` and the templates model file —
  confirm no accidental edits landed near the fields this task does touch in the same
  file).
- `uv run mypy .` exits 0 (no new errors from removed fields' type references).
- `uv run pytest tests/ -v` passes at the same rate as the P0-T2/T3 baseline, minus the
  21 deleted `test_state_machine.py` tests and whatever `test_pipeline.py` adjustments
  step 6 required — no *new*, unexplained failures.

## Tests

- Delete `tests/unit/agents/test_state_machine.py` in full (tests a deleted feature).
- Update `tests/unit/pipeline/test_pipeline.py:311`
  (`test_fan_out_any_failure_fails_stage_even_when_non_critical`) per step 6 of
  Implementation approach — either delete it or rewrite it to assert the underlying
  always-fail-fast-on-fan-out-failure behavior without referencing the now-nonexistent
  `critical` field.
- Update `tests/unit/audio/conftest.py:209` and
  `tests/integration/audio/test_lyrics_analyzer_integration.py:33` to remove references
  to the deleted `checkpoint_dir`/`checkpoint` fields.
- No new tests are added by this task — it is a removal, not new behavior. If any
  remaining test asserts on `ExecutionPattern.PARALLEL`/`CONDITIONAL`'s mere existence
  (as opposed to their inert behavior), find and update it as part of the enum-member
  removal (search `tests/` for `ExecutionPattern.PARALLEL`/`ExecutionPattern.CONDITIONAL`
  before finalizing).

## Verification commands

```bash
# Confirm deletions
test ! -f packages/twinklr/core/agents/token_budget_manager.py && echo OK
test ! -f packages/twinklr/core/agents/state_machine.py && echo OK
test ! -f packages/twinklr/core/pipeline/stages.py && echo OK
test ! -f tests/unit/agents/test_state_machine.py && echo OK

# Confirm zero remaining references (inspect hits manually for false positives)
grep -rn "TokenBudgetManager\|OrchestrationStateMachine\|checkpoint_dir\|ExecutionPattern.PARALLEL\|ExecutionPattern.CONDITIONAL" packages/ tests/ scripts/ docs/

# Confirm the do-NOT-touch fields are untouched
git diff packages/twinklr/core/config/models.py | grep -E "success_threshold|max_iterations|judge_agent|channel_defaults|Template.defaults"
# (expect no output, or output only from context lines, not actual +/- changes to these fields)

uv run mypy .
uv run pytest tests/ -v
```

## Effort & risk

**M** (medium — five independent-but-file-overlapping deletions, each individually
small). Main risks: (1) accidentally touching one of the explicit do-NOT-touch fields
while editing the same files (`config/models.py` in particular holds both dead fields
this task removes and live fields it must not touch) — mitigate with the `git diff`
scoping check in Verification commands; (2) under- or over-scoping the `critical`
grep (a common English word) when confirming zero remaining references — inspect each
hit, don't trust the raw count; (3) `test_fan_out_any_failure_fails_stage_even_when_non_critical`'s
disposition (delete vs. rewrite) is a judgment call — prefer rewriting to preserve the
regression-test value of "fan-out failure is unconditional" if that's a behavior worth
continuing to pin, since deleting a test is easy to do carelessly and losing coverage of
real executor behavior (not just the dead field) would be a net loss.
