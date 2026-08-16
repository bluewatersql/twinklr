# P2P-T9 — Judge feedback repair (D4)

Phase: 2P (Creative Quality, Measured) · Lane: Gate (in `agents/shared`) · Executor: opus · Verifier: opus · Depends on: P2P-T1 (rebases on it); must land before P2P-T13

⚖ **Owner-decision-bearing.** D4 flipped the default in v3: iterative judging is
**kept**, and the burden of proof now sits on removal. The owner reviews that this
task fixes the loop rather than quietly narrowing it, and reviews the
`success_threshold` semantics chosen in §3.

## Objective

Make the iteration loop capable of the thing it was built to do. Give the judge memory
of its own prior verdicts within a run; stop making ONESHOT schema repair a blind
full-cost resample; and make the two configuration knobs that control the loop
actually work — one is inert, the other crashes at its documented value.

## Evidence & background

Findings: **P3-F7** (the whole `judge_context_builder` hook is dead and its signature
can't carry feedback), **P3-M-A** (`success_threshold` inert), **P3-M-B**
(`max_iterations=0` crashes), **P3-M-D** (ONESHOT repair is blind), **D4** (keep
iteration, fix the feedback defects). Related: **P3-F9** (≈60-call ceiling),
**P3-M-F** (retry amplification ≤9 requests/call), **P3-M-G** (JSON-parse failures get
zero retries — owned by P2P-T11).
Sources: `changes/twinklr-reactivation-review/reviews/phases/llm-agents-and-planning.md`
§4.2, §10 (P3-F7, P3-M-A/B/D); `.../reviews/verification.md` "Phase 3";
`.../reviews/reactivation-proposal.md` D4.

### D4 quoted

> **D4 — Judge/iteration** *(flipped in v3)*: v1/v2's single-pass default was
> cost-lens residue. **New default: fix the feedback defects (judge memory, blind
> ONESHOT repair) and KEEP iterative refinement**; the D11 harness argues iteration
> *down* if it proves valueless — the burden of proof now sits on removal, matching
> the quality-first axis.

### P3-F7 — the dead hook, quoted in full (mechanics the executor must not re-derive)

> `moving_heads/orchestrator.py:97-138` defines `build_judge_variables`;
> `__init__.py:22,50` exports it; grep-verified **no caller**. `run()` (`:309-317`)
> omits `judge_context_builder`, so `controller.py:501-541` supplies planner vars +
> `plan`. Consequence: `previous_feedback`/`previous_issues` are never set, so
> `judge/user.j2:72-90` never renders and the judge has no memory of its own prior
> verdicts across iterations of the same run.

> **EXTENDED AT VERIFICATION — the remedy is larger than wiring one call.** (1) The
> `judge_context_builder` parameter (`controller.py:270`) is grep-verified to have
> **no caller anywhere**, not just in moving-heads: all three orchestrators
> (`macro_planner/orchestrator.py:271-278`, `moving_heads/orchestrator.py:309-317`,
> `group_planner/orchestrator.py:308-315`) call `controller.run()` without it. The
> whole extension point is dead and *every* judge in the system runs on
> `_prepare_judge_variables`. (2) The hook's signature is
> `Callable[[TPlan, int], dict[str, Any]]` — plan and iteration number only, with
> **no parameter through which prior verdicts, feedback, or issues could be passed**.
> `IterationContext` holds that history (`controller.py:119-120`) and is never offered
> to the builder. Wiring `build_judge_variables` in as-is would therefore still leave
> the judge without its history; the signature must change first. This is a design
> gap, not a missing argument.

And from §4.2:

> This is not a template guard doing its job — it is a wiring gap the `is defined`
> guards silently absorb.

**Re-verified in this tree (2026-08-13):** `controller.py:270` declares
`judge_context_builder: Callable[[TPlan, int], dict[str, Any]] | None = None`;
`:400-403` selects it if not None, else `_prepare_judge_variables(...)` at `:501`.
`build_judge_variables` exists at `moving_heads/orchestrator.py:97` and is exported at
`moving_heads/__init__.py:21,50`. The only other `_build_judge_variables` is
`group_planner/holistic.py:302`, a *different* private function on the holistic path.

**Design consequence, stated so the executor does not take the cheap path:** wiring
`build_judge_variables` into `controller.run()` as-is is NOT the fix. The signature
must change so the builder receives the verdict history, or the orchestrator must
close over it. Either way, `IterationContext`'s accumulated verdicts/revision
requests (`controller.py:119-120`) must reach the judge's variables.

### P3-M-A — `success_threshold` is inert, quoted

> `AgentOrchestrationConfig.success_threshold` (`config/models.py:100`, default 70,
> `ge=0 le=100`, "Minimum judge score to accept plan") threads correctly all the way
> to `IterationConfig.approval_score_threshold` via each orchestrator's
> `min_pass_score`. It then does nothing: the controller's decision reads **status
> only** (`controller.py:431`, `if verdict.status == VerdictStatus.APPROVE`), and
> status is force-reconciled to **hardcoded** 7.0/5.0 boundaries by
> `JudgeVerdict._expected_status_for_score` (`judge/models.py:132-137`). The
> threshold is compared against nothing. **A new member of the dead-config class**
> (P3-F6, P7-M2) and the most deceptive one, because the plumbing is complete and
> correct right up to the point of use. **Consequence for Stage 2**: an ablation arm
> that varies judge strictness would compare two identical configurations and report a
> null result that means nothing.

**Re-verified:** `AgentOrchestrationConfig.success_threshold` is at
`config/models.py:100` (`default=70, ge=0, le=100`);
`JudgeVerdict.enforce_status_matches_score` overrides status via
`object.__setattr__` on the frozen model, and `_expected_status_for_score` hardcodes
`>= 7.0 → APPROVE`, `>= 5.0 → SOFT_FAIL`, else `HARD_FAIL`.

And the qualification attached to the ST-2 strength (P3-F36):

> The same validator that makes this a strength is also what kills the
> `success_threshold` knob … The mechanism is worth keeping, but it must be
> *reworked* rather than preserved verbatim if threshold configurability is ever
> wanted — the guard and the dead knob are the same line of code. Any Stage 8 item
> that proposes keeping this as-is while also making strictness configurable is
> internally inconsistent.

### P3-M-B — the documented `max_iterations=0` crashes, quoted

> `AgentOrchestrationConfig.max_iterations` (`config/models.py:80-82`) declares
> `ge=0` with the description "Maximum judge/iterate loops (**0=skip judge**)". The
> value validates there, is read by `MovingHeadStage` (`stage.py:169-172`), and is
> passed into `IterationConfig.max_iterations`, which declares `ge=1`
> (`controller.py:56`) — a `ValidationError` at construction. The one documented way
> to turn the judge off is an actively failing value, not merely a no-op. Note this
> is the config knob Stage 2 would most want for its macro-ablated arm.

**Re-verified:** `config/models.py` declares `max_iterations: int = Field(default=3,
ge=0, description="Maximum judge/iterate loops (0=skip judge)")`;
`controller.py:56` declares `max_iterations: int = Field(ge=1, le=10, default=3, ...)`.

### P3-M-D — ONESHOT repair is blind, quoted

> `_execute_with_repair_async` appends only the formatted validation errors as a new
> user message (`async_runner.py:390-396`); the model's failing response is **never**
> appended as an assistant turn. For CONVERSATIONAL agents the provider stores the
> assistant turn itself (`openai.py:449-451`), so the model can see what it produced.
> For **ONESHOT** agents there is no such store — so every repair attempt is a **blind
> full-cost resample**: the model is told "fix these errors" about output it cannot
> see. This affects every judge (`mh_judge` ≤3, `macro_judge` ≤5), the audio-profile
> and lyrics agents, and the holistic corrector. **This answers §5's open question**
> ("does repair feedback actually work?") structurally rather than empirically: on
> ONESHOT specs it cannot. It also materially changes P3-F9's cost ceiling — a large
> share of those ~60 calls are uninformed retries.

Line numbers are hints from baseline `aa8d325`; re-verify before editing.

## Current behavior

- Every judge in the system runs on `_prepare_judge_variables` (planner vars + plan).
  `previous_feedback` / `previous_issues` are never set; `judge/user.j2:72-90` never
  renders; the judge evaluates iteration 3 with no memory that it rejected 1 and 2.
- `success_threshold` is fully plumbed and compared against nothing.
- `max_iterations=0`, the documented way to skip the judge, raises `ValidationError`.
- ONESHOT repair attempts are blind full-cost resamples.
- Worst case ≈60 LLM calls per song (P3-F9), of which a large share are uninformed
  retries, multiplied by up to 3 SDK-level HTTP attempts each (P3-M-F).

## Target behavior

### 1. Judge memory of its own verdicts

The judge receives its prior verdicts, revision requests and issues for the current
run. Two acceptable designs; pick one, document why:

- **(a) Change the hook's signature** so `judge_context_builder` receives the
  `IterationContext` (or an explicit history argument) alongside plan and iteration,
  and wire the existing `build_judge_variables` through it in all three orchestrators.
- **(b) Have the orchestrator close over verdict history** and pass judge variables
  directly, deleting the dead hook entirely.

Either way: `judge/user.j2`'s iteration-history block must render with real content by
iteration 2, asserted on the **rendered output**. If the hook survives, it must have a
caller; if it does not, delete it and its export — leaving a dead extension point
after this task is a regression of the task's own purpose.

### 2. ONESHOT repair shows the model its failing output

`_execute_with_repair_async` appends the model's failing response (truncated to a
sane bound) alongside the formatted validation errors, so a ONESHOT repair attempt is
informed rather than a resample. Constraints:

- Do not stuff unbounded model output into the next request — bound it and say so in
  the message.
- CONVERSATIONAL agents already see their own turn via the provider store; do not
  double-append for them.
- P2P-T11 shrinks this loop to refusal/truncation handling. This task must leave the
  repair path in a shape T11 can narrow, not restructure it in a way T11 must undo.

### 3. `success_threshold` — wire or delete, explicitly

The knob and the guard are the same line of code. Decide and implement one:

- **Wire it**: `_expected_status_for_score`'s boundaries become parameters fed from
  `IterationConfig.approval_score_threshold` (with the 7.0/5.0 pair as defaults), and
  the controller's approval decision honours the configured threshold. The *property*
  ST-2 protects — a verdict's status can never contradict its score — is preserved;
  only the boundary's source changes.
- **Delete it**: remove `success_threshold` from `AgentOrchestrationConfig`, remove
  `min_pass_score` threading, remove `approval_score_threshold`, and document the
  fixed 7.0/5.0 policy.

**Wiring is strongly preferred**, because P2P-T13's arms would otherwise be unable to
vary judge strictness at all ("an ablation arm that varies judge strictness would
compare two identical configurations and report a null result that means nothing").
A cache note: `min_pass_score` is in the planner cache keys yet behaviorally inert
today, so "a threshold change forces full uncached re-plans that cannot differ (an
experiment confounder)" — wiring it makes the key honest.

### 4. `max_iterations=0` works as documented

`0 = skip judge` must either work (plan once, no judging, return the plan) or the
documentation and the `ge=0` bound must change together. Preferred: **make 0 work** —
it is the knob P2P-T13's macro-ablated arm needs. The `IterationConfig.max_iterations`
`ge=1` constraint and the `AgentOrchestrationConfig` `ge=0` description must stop
contradicting each other either way.

### Non-goals

- Structured outputs / `json_object` → `json_schema` (**P2P-T11**).
- P3-M-G (unparseable JSON gets zero retries) — **P2P-T11** owns retry parity.
- Per-call token accounting (**P1P-T9**).
- The five deterministic auto-repair passes on the display path (P3-F10) — salvage is
  a later concern.
- Deleting the iteration loop. D4 flipped the default: iteration stays; P2P-T13's
  evidence is what could argue it down later.

## Implementation approach

Files/symbols (re-verify first):

- `packages/twinklr/core/agents/shared/judge/controller.py` — `IterationConfig`
  (`:38`, `max_iterations` `:56`, `approval_score_threshold` `:68`),
  `IterationContext` (`:98`, history at `:119-120`), `run` (`:261`,
  `judge_context_builder` `:270`, judge-var selection `:400-403`, approval `:431`,
  max-iter `:449`, token budget `:452`), `_prepare_judge_variables` (`:501`).
- `packages/twinklr/core/agents/shared/judge/models.py` —
  `enforce_status_matches_score`, `_expected_status_for_score`,
  `RevisionRequest.from_verdict` (keep: ST-2/P3-F36 strength).
- `packages/twinklr/core/agents/sequencer/moving_heads/orchestrator.py` —
  `build_judge_variables` (`:97`), `run` (`:309`).
- `packages/twinklr/core/agents/sequencer/{macro_planner,group_planner}/orchestrator.py`
  — the other two `controller.run()` call sites.
- `packages/twinklr/core/agents/sequencer/moving_heads/prompts/judge/user.j2` — the
  iteration-history block.
- `packages/twinklr/core/agents/async_runner.py` — `_execute_with_repair_async`.
- `packages/twinklr/core/config/models.py` — `AgentOrchestrationConfig`.
- `packages/twinklr/core/agents/sequencer/moving_heads/stage.py` — reads
  `context.job_config.agent.max_iterations`.

Sequencing constraints copied verbatim from the plan:

> - T1 and T9 both touch `agents/shared`+schemas: T1 lands first; T9 rebases.
> - **Verification currency**: evidence in specs is from baseline `aa8d325`.
>   Executors must re-verify cited line numbers before editing.

Rebase note: P2P-T1 deletes `JudgeVerdict.overall_assessment` and `.score_breakdown`
and the three `Issue` fields. Do not reintroduce them here; the judge's *memory* is
built from `RevisionRequest`/verdict status/score/issues that survive T1.

Documentation constraint: P7-M2 records that `docs/user-guide.md` documents these
knobs as live while every one fails silently. Whatever this task decides for each
knob, the user guide must match at merge — a knob that now works and a knob that was
deleted both change that document.

## Acceptance criteria

1. By iteration 2, the judge's rendered user message contains its prior verdict
   summary and issues — asserted on rendered output, not on template source.
2. `judge_context_builder` either has a real caller with a signature able to carry
   history, or is deleted along with its export. No dead extension point remains.
3. A ONESHOT repair attempt's request contains the model's failing output (bounded)
   in addition to the validation errors; a CONVERSATIONAL attempt does not
   double-append.
4. `success_threshold` is wired (a configured threshold changes which verdicts are
   accepted, asserted with a fake judge returning a fixed score) or deleted with the
   documentation updated. If wired, `JudgeVerdict` still cannot express a status
   inconsistent with its score under the configured boundaries.
5. `max_iterations=0` no longer raises: it either skips judging and returns the plan,
   or the config bound and its description are changed together so no documented value
   crashes.
6. `docs/user-guide.md`'s entries for these knobs describe the post-task reality.
7. No increase in worst-case call count. Report the new ceiling explicitly against
   P3-F9's ≈60 (informed repairs should reduce attempts, not add calls).
8. `make validate` check-only forms pass.

## Tests

TDD — failing first; extend `tests/unit/agents/shared/judge/test_controller.py`,
"the only test that exercises the iteration loop as a loop":

1. `test_judge_receives_prior_verdicts_on_second_iteration` — fake planner + fake
   judge that rejects once; assert the judge's variables (and rendered prompt) carry
   the first verdict.
2. `test_judge_history_block_renders` — rendered-output assertion on `judge/user.j2`.
3. `test_oneshot_repair_includes_failing_output` — fake provider records the request;
   assert the failing payload is present and bounded.
4. `test_conversational_repair_does_not_double_append`.
5. `test_success_threshold_changes_acceptance` — same judge score, two configured
   thresholds, two different outcomes. This is the test whose absence let P3-M-A
   survive.
6. `test_status_cannot_contradict_score_under_configured_threshold` — ST-2's property
   preserved after rework.
7. `test_max_iterations_zero_skips_judge` (or the documented alternative).
8. `test_call_ceiling_not_increased` — a bounded fake provider counting calls for a
   worst-case run.

## Verification commands

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy .
uv run pytest tests/unit/agents/shared/judge -q
uv run pytest tests/unit/agents -q
uv run pytest -k "judge or iteration or repair" -q
```

No paid API calls required — every behavior here is testable against a fake provider,
which is the point of the fake-provider seam. One LOCAL-ONLY live run (**one song,
≤60 LLM calls**) may be used to sanity-check that a real judge's second-iteration
prompt looks right; not required for merge.

## Effort & risk

**M–L.** Main risk: reworking `enforce_status_matches_score` is touching the one
mechanism the review named a genuine strength. Mitigation: preserve the *property*
(status can never contradict score) as a test, change only the boundary's source, and
have the verifier check the property explicitly rather than the implementation.
Second risk: the judge-memory fix changes what the judge sees, so plans change and
cached results are no longer comparable — land after P1P-T9's prompt-content hashing
so cache invalidation is honest, and note the expected plan-output change in the
handoff so P2P-T13 does not attribute it to an arm. Third risk: making informed repair
*more* expensive per attempt (bigger requests) — bounded by the truncation rule and
checked by criterion 7.

## Backlog addition (P1P-T9 verification, 2026-08-13)
min_pass_score is present in the three planner cache keys yet behaviorally inert
(the verdict enforcer hardcodes 7.0/5.0) — changing it forces spurious full
uncached re-plans that cannot differ. Resolve here with the threshold wiring:
either make it behavioral or remove it from the keys.

## Implementation handoff — 2026-08-14 (pending independent verification and owner review)

### Implemented contract

- Iteration is retained. The live `judge_context_builder` now receives the same-run
  `IterationContext`. The moving-head orchestrator wires its domain-specific builder
  through a closure over `MovingHeadPlanningContext`; macro and group judges use the
  controller's common shaping path. Both paths receive prior verdict summaries,
  feedback, issues, and revision requests. History is created inside each `run()` and
  cannot cross jobs or judge roles.
- `success_threshold` is wired. The public config remains the only 0-100 scale and
  converts once through `min_pass_score`; `IterationConfig` and every judge prompt use
  the resulting 0-10 approval boundary. `JudgeVerdict.with_score_thresholds()`
  reconciles the retained status immediately after parsing, preserving the invariant
  that status cannot contradict score under the active boundary. The 5.0 soft-fail
  boundary remains the default and is clamped to the approval boundary for thresholds
  below 5.0.
- `max_iterations=0` now means: run the planner once, run deterministic heuristic
  validation, and skip the LLM judge. A heuristic-valid plan succeeds with no final
  verdict; a heuristic-invalid plan fails without a judge call.
- ONESHOT Pydantic-validation repair includes the failing response in the next request,
  deterministically serialized and bounded to 6,000 characters with an explicit
  truncation notice. CONVERSATIONAL repair remains errors-only because the provider's
  conversation store already retains the assistant turn.
- Refusal, truncation, content-filter, empty-response and malformed-response retry
  behavior from P2P-T11 is unchanged. Per-attempt usage is still appended before
  classification, so repair/refusal token accounting is unchanged.
- Moving-head cache identity now includes `max_iterations` and `min_pass_score`,
  matching macro/group. All edited prompt packs remain covered by `spec_prompt_hash`,
  so history/threshold prompt changes invalidate cached plans honestly.
- The display-pipeline factory's stale 0-1-scale default (`0.6`) is corrected to
  `7.0` on the controller's 0-10 scale. Leaving it in place would have turned the
  newly-live threshold into an accidental near-zero approval boundary for group plans.

### Request ceiling

No call layer was added. A three-cycle controller still makes at most three planner and
three judge agent invocations (six). Under P2P-T11 each invocation retains its existing
normal ceiling of two logical responses times three provider transport attempts: one
three-cycle controller therefore remains at 12 logical responses / 36 HTTP attempts
normal, or 48 HTTP attempts on the observable strict-capability fallback path. The
whole-song ceilings recorded by P2P-T11 remain 120 logical / 360 HTTP normal and 480
fallback against P3-F9's approximate 60 base invocations. T9 increases only the bounded
repair-request payload, not the request count.

### Verification evidence

- Discriminating tests were observed red on the pre-fix implementation for the dead
  history hook, inert threshold, crashing zero value, and blind ONESHOT repair. The
  unchanged six-call controller ceiling passed before and after.
- `tests/unit/agents`: **1,097 passed / 1 skipped**.
- `-k "judge or iteration or repair"`: **140 passed / 2 skipped**.
- Provider + structured-output + token-attribution + cache suites:
  **129 passed**.
- Golden selection: **72 passed / 8 skipped**, byte-stable.
- Full suite: **4,993 passed / 35 skipped**.
- `ruff format --check .`: **1,295 files already formatted**;
  `ruff check --no-cache .`: **clean**; `mypy .`: **702 files clean**.
- `make validate` itself deliberately refuses an author worktree with uncommitted
  changes. Its check-only equivalents above all passed; the orchestrator should run
  the wrapper after committing/integrating.

No live or paid API call was made. At this authoring snapshot, owner review remained
required for the retained iteration policy and the wired configurable
approval-threshold semantics; the later decision is recorded below.

## Owner decision — 2026-08-16

The owner explicitly accepted retained iterative judging, configurable approval
threshold semantics, and `max_iterations=0` behavior. This satisfies P2P-T9's
decision-bearing review; it does not satisfy the still-pending Phase 2P empirical exits.
