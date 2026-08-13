---
type: change
status: active
area: agents
updated: 2026-08-13
---

# Phase 3 — LLM Agents & Planning

_Stage 3 phase review. Baseline `aa8d325`. Author: general-purpose (opus)
"phase3-author". Read-only against application code; this file is the only write
target. **Verified 2026-08-13 (opus critic, non-author) — 22 ACCEPTED, 12 REVISED,
12 verifier-added findings adopted (P3-M-A..M-L). See `reviews/verification.md`
"Phase 3" for the condensed verdict record.** This revision applies every required
correction; original author text is preserved where the verifier accepted it.
Corrections are marked inline as "REVISED AT VERIFICATION" where the author's
original claim was wrong rather than merely imprecise._

_The two most load-bearing findings were confirmed airtight by the verifier: **F5**
(the shipped moving-head planner is blind to lyrics — three independent locks: an
`extra="forbid"` model, model-object passing, and phantom field names appearing in
exactly 4 `.j2` lines and no Python; the Lyric Context block renders the single line
"Has Lyrics: Yes") and **F13** (few-shot examples never delivered — both bugs
confirmed, and worse than stated: the call logs assert a delivery that never
happened)._

_Evidence basis: the author read `async_runner.py`, `spec.py`, `providers/{base,
openai,factory}.py`, `shared/judge/{controller,models}.py`, all three sequencer
orchestrators, `sequencer/{macro_planner,moving_heads}/specs.py`,
`moving_heads/{stage,context,heuristic_validator}.py`, and
`group_planner/orchestrator.py` in full, plus targeted greps. Two read-only
subagents (opus) performed the exhaustive sweeps this phase required: an
**assets-package audit** (all 9 modules, ~2 500 LOC — first read in this review) and
a **prompt-pack/schema co-design audit** (all 11 packs, 50 files, plus a
field-by-field consumer grep of every LLM response schema in scope). Their citations
are reproduced here and were spot-checked by the author on the load-bearing claims
(V2, V-agents, `recommended_sections`, `planner_hints`, pack.yaml). Absence claims
marked "grep-verified" are exhaustive-search inferences, not direct observation._

## 1. Scope & exclusions

**In scope, read**: `core/agents/` in its entirety —
`async_runner.py`, `spec.py`, `result.py`, `state.py`, `issues.py`,
`schema_utils.py`, `taxonomy_utils.py`, `_paths.py`, `state_machine.py`,
`token_budget_manager.py`; `prompts/{loader,renderer,sanitize}.py`;
`providers/{base,openai,anthropic,factory,conversation,errors}.py`;
`shared/judge/{controller,feedback,models}.py`;
`sequencer/{macro_planner,group_planner,moving_heads}/` (orchestrators, specs,
context, context_shaping, heuristics/validators, stages);
`audio/{profile,lyrics}/` (orchestrator, context, models, spec, stage, validation);
`assets/` (all 9 modules); `analytics/repository.py`; `context/`; `logging/`.
Plus `core/sequencer/planning/` models as the planner-facing contract, and **all 11
runtime prompt packs** under `packages/twinklr/core/**/prompts/` (Jinja2 application
source — reviewed for prompt/schema co-design, not merely for template validity).

**Excluded / owned elsewhere**: the `PipelineExecutor`, `PipelineContext`, and
`session.py` side of the FAN_OUT token race (phase 1 — this review owns the
`async_runner` half only); `core/sequencer/vocabulary` as a contract definition
(phase 4 owns it; this phase reviews as consumer); the moving-head renderer,
template registry, and curve compilation (phase 4); display renderer, theming
catalogs, and `.xsq` I/O (phase 5); `core/api/llm/openai/client.py` internals
(phase 1 owns `core/api/`, but its *duplication* with the provider is reported here
because both live on the agent call path); test correctness and suite pass/fail
(Stage 4).

**N/A dimensions**: none of the assigned dimensions is N/A for this phase. Every
one — iteration-loop correctness, prompt-injection surface, provider abstraction,
Pydantic/structured-output readiness, observability, test realism, cost accounting —
has material findings below.

## 2. Purpose, entry points, contracts, state, invariants, dependencies, consumers

**Purpose.** `core/agents/` is the LLM boundary for the **shipped pipeline**. Every
model call on the moving-heads path goes through `AsyncAgentRunner.run()`
(`async_runner.py:69`), as does the assets subsystem's prompt enricher
(`assets/prompt_enricher.py:147`).

**REVISED AT VERIFICATION (P3-M-C)** — the author's original "every model call in
Twinklr, without exception" is **false repo-wide**. Three surfaces call an LLM
without passing through the runner: `feature_engineering/normalization/
llm_review.py:71` (`chat.completions.create` directly),
`core/api/llm/openai/client.py:355,589,682` (`responses.create`, used by
`recipe_builder`), and `assets/stage.py:289` (`AsyncOpenAI()` for the image API,
a different API surface). All three are outside the shipped path, so the
one-chokepoint property holds where it matters — but it is a property of the
moving-heads pipeline, not of the repository, and §9's "single LLM chokepoint"
claim must be read with that qualification.

**Entry points.** Five pipeline stages construct orchestrators:
`audio/profile/stage.py:75`, `audio/lyrics/stage.py:84`,
`sequencer/macro_planner/stage.py:100`, `sequencer/moving_heads/stage.py:175`
(the four on the shipped path), plus `sequencer/group_planner/stage.py:143`,
`group_planner/holistic_stage.py:113`, `group_planner/corrector_stage.py:229`, and
`assets/stage.py:154` (display path only). A legacy duplicate exists at
`pipeline/stages.py:219` (confirmed dead in discovery §5).

**Core contract.** `AgentSpec` (`spec.py:18`) is a frozen Pydantic model carrying
`name`, `prompt_pack`, `response_model`, `mode`, `model`, `temperature`,
`max_schema_repair_attempts`, `default_variables`, `token_budget`. The runner:
merges default variables → auto-injects `response_schema` from
`model_json_schema()` (`async_runner.py:93-94` → `schema_utils.py:37`) →
auto-injects ~25 categorical enums (`taxonomy_utils.inject_taxonomy`,
`async_runner.py:97`) → loads and renders the Jinja2 pack → builds
developer/system/examples/user messages (`:203-227`) → executes with a
client-side schema-repair loop (`:313-398`) → logs → returns `AgentResult`.

**State.** Three stateful surfaces. (1) `AgentState` carries `conversation_id` and
`attempt_count` for CONVERSATIONAL agents; the provider holds the actual message
history in an in-process dict (`providers/openai.py:77`). (2) `IterationContext`
(`controller.py:98`) accumulates verdicts, revision requests, and token totals
across the loop. (3) `IssueRepository` (`analytics/repository.py:62`) persists
judge issues as JSONL under `data/agent_analytics/` and is **enabled by default**
(`controller.py:76-83`), feeding historical issue categories back into the
developer prompt on the next run (`controller.py:313-324`).

**Invariants that hold.** Prompt rendering is `SandboxedEnvironment` +
`StrictUndefined` (`renderer.py:32-37`). Response schemas and enum vocabularies are
machine-derived from the Pydantic/enum source — the author found **zero
hand-authored schema duplicates** in any prompt (confirming discovery). Judge
`status` cannot contradict `score`: `JudgeVerdict.enforce_status_matches_score`
(`models.py:98-120`) overwrites the LLM's status via `object.__setattr__` on the
frozen model. `AgentSpec` and `IterationConfig` are frozen with `extra="forbid"`.

**Invariants that do not hold.** `pack.yaml` declares required variables,
`max_iterations`, and pack versions that nothing reads (§4). `AgentSpec.token_budget`
is threaded from four orchestrators into every spec and read by nobody. The
`examples` message slot is populated by the loader and then discarded for every pack
that has examples.

**Dependencies.** `openai` SDK (Responses API), `anthropic` (optional extra),
`pydantic` v2, `jinja2`, and — critically — `core/sequencer/planning` and
`core/sequencer/vocabulary` for the plan schemas and categorical taxonomies. The
agents package imports the vocabulary; the vocabulary does not import agents. That
direction is clean.

**Consumers.** `core/pipeline/definitions/{moving_heads,display}.py` (stage graphs);
`core/sequencer/moving_heads/pipeline.py` consumes `ChoreographyPlan` (five fields);
`core/sequencer/display/` consumes `SectionCoordinationPlan`;
`reporting/evaluation/generator.py` consumes plans for reports.

## 3. Representative execution paths inspected

**Path A — shipped moving-heads run (traced end to end).**
`AudioProfileStage` → `AudioProfileOrchestrator.run` → one ONESHOT gpt-5.2 call →
`AudioProfileModel`. In parallel, `LyricsStage` → one ONESHOT gpt-5.2 call →
`LyricContextModel`. Then `MacroPlannerStage` → `MacroPlannerOrchestrator`
(`orchestrator.py:271`) → `StandardIterationController.run` → up to 3 × (planner
CONVERSATIONAL gpt-5.2 → `_canonicalize_section_ids` → `MacroPlanHeuristicValidator`
→ judge ONESHOT **gpt-5.2**) → `MacroPlan`. Then `MovingHeadStage`
(`moving_heads/stage.py:194`) → `MovingHeadPlannerOrchestrator`
(`orchestrator.py:309`) → up to 3 × (planner CONVERSATIONAL gpt-5.2 →
`HeuristicValidator` (no repair) → judge ONESHOT gpt-5-mini) → `ChoreographyPlan` →
renderer.

**Path B — schema repair.** `_execute_with_repair_async` (`async_runner.py:335`)
loops `max_schema_repair_attempts + 1` times, appending the formatted Pydantic
errors as a new user message each failure (`:396`) and re-calling the provider.
For CONVERSATIONAL specs this appended message is the one the provider sees
(`:453-457` takes `user_messages[-1]`), so repair does work in conversational mode —
but see §4 for what else that line drops.

**Path C — display/group planner (unreachable from CLI).** FAN_OUT per section →
`GroupPlannerOrchestrator.run` → ultra-short branch (`orchestrator.py:260`) or full
loop → five deterministic repair passes inside the validator closure
(`orchestrator.py:450-483`) → section judge (gpt-5-mini) → aggregate → holistic
judge → holistic corrector.

**Path D — assets (unreachable; paid).** `AssetCreationStage.execute`
(`assets/stage.py:81`) → deterministic `extract_asset_specs` → catalog reuse check →
concurrent gpt-5-mini prompt enrichment (Semaphore 5) → second reuse check →
concurrent `images.generate` on `gpt-image-1.5` → catalog merge + save.

## 4. Implementation assessment

### 4.1 The runner and prompt layer

The `AsyncAgentRunner` is the strongest single piece of design in this phase. One
execution engine, one repair loop, one logging path, and schema/taxonomy injection
that structurally cannot drift from the Pydantic source. That last property is real
and worth preserving verbatim.

Three defects sit inside it.

**Few-shot examples never reach any model.** Two independent bugs. The loader looks
only for `examples.jsonl` (`prompts/loader.py:86,201`), so the audio-profile pack's
`examples/example_1.json` and `example_2.json` — which `audio_profile/pack.yaml`
explicitly lists — are never opened. And `_call_conversational_async` rebuilds the
request from developer + system + `user_messages[-1]` only
(`async_runner.py:452-457`), discarding every example turn that `_build_messages`
appended at `:221-222`. The only two packs that *have* an `examples.jsonl` —
`macro_planner/prompts/planner` and `group_planner/prompts/planner` — are both
`AgentMode.CONVERSATIONAL` (`macro_planner/specs.py:34`, `group_planner/specs.py:39`).
Net: **no prompt pack in this repository delivers few-shot examples at runtime**, and
the `group_planner` examples (34 messages, verified schema-correct against
`SectionCoordinationPlan`) represent authoring effort that has never influenced a
single token.

**`pack.yaml` is inert.** Grep-verified: the string `pack.yaml` appears in zero `.py`
files. The loader's file list is hardcoded and exhaustive (`loader.py:161-212`);
`system.j2` is the only enforced requirement. Seven packs declare `variables.required`,
`metadata.max_iterations`, `templates.*`, and `examples` — none of it is read. Worse,
the two packs that record a version record it **inverted**: `lyrics/pack.yaml` declares
`pack_version: "2.0"` while `audio/lyrics/orchestrator.py:181` writes `"1.0"`;
`audio_profile/pack.yaml` declares `"1.0"` while `audio/profile/orchestrator.py:174`
writes `"2.0"`. Provenance is wrong for both agents, in opposite directions. Four packs
have no `pack.yaml` at all (`group_planner/planner`, `moving_heads/planner`,
`moving_heads/judge`, `assets/asset_prompt_enricher`).

**Token deltas are computed across `await` boundaries on a shared counter, and the
shipped path is already affected.** `run()` snapshots
`self.provider.get_token_usage()` at `:86` and again at `:120`, then reports the
difference as this call's usage. The provider's counter is process-global and shared
across all concurrent agents (one memoized provider per session).

**REVISED AT VERIFICATION** — the author's original scoping ("on the shipped
moving-heads path planning is sequential, so the race does not currently fire") was
**wrong and has been deleted**. The `profile` and `lyrics` stages share a single
executor wave under `asyncio.gather` against the same memoized provider, so two
concurrent agents interleave their snapshots on the only production path. **Every
per-stage token figure the shipped pipeline reports is already wrong today** — this
independently confirms P1-F27 from the runner side. `IterationConfig.token_budget`
enforcement (`controller.py:452`) reads the same accumulated figure and would
mis-enforce if fed.

**Fix scope is larger than a one-line change.** The correct per-call number exists —
`providers/openai.py:361-367` populates `LLMResponse.metadata.token_usage` — but
`_execute_with_repair_async` returns only `(response.content, repair_attempts)`
(`async_runner.py:344,350`), discarding the metadata. Fixing this requires threading
the `LLMResponse` (or its `TokenUsage`) out through the repair loop and into both
`AgentResult` and `_safe_log_complete`, then summing across repair attempts.
Phase 1 owns the executor/session half; neither fix alone is sufficient.

### 4.2 The iteration loop — correctness and feedback quality

**Termination is correct.** Four exits, all reachable: approval
(`controller.py:431`), max iterations (`:449`), token budget (`:452`, currently
unfed), planner/judge failure (`:342`, `:409`). The loop cannot spin: `for iteration
in range(self.config.max_iterations)` with `max_iterations` bounded 1–10 by the
field constraint. Heuristic-validation failure `continue`s without judging, which is
the right ordering — no tokens are spent judging a structurally invalid plan.

**Feedback quality is mixed, and the moving-heads path gets the worst of it.**
`RevisionRequest.from_verdict` (`models.py:218-271`) is genuinely well built:
it prefers structured `targeted_actions` over free-text `fix_hint`, derives priority
from status and blocking issues, and preserves judge-identified strengths as an
explicit "do not change" list. This is more specific than typical LLM-critic
plumbing. But:

- **The moving-heads judge is fed the planner's variables, not judge variables.**
  `build_judge_variables` (`moving_heads/orchestrator.py:97-138`) is defined,
  exported (`__init__.py:22,50`), and **never called** — grep-verified: the only
  hits are the definition and the export. `MovingHeadPlannerOrchestrator.run`
  (`:309-317`) calls `controller.run(...)` without `judge_context_builder`, so the
  controller falls back to `_prepare_judge_variables` (`controller.py:501-541`),
  which copies the planner's `initial_variables` and adds `plan`. The practical
  consequences: `previous_feedback` and `previous_issues` are never supplied, so the
  judge's iteration-history block (`judge/user.j2:72-90`) never renders and the judge
  evaluates iteration 3 with no memory that it already rejected iterations 1 and 2;
  and the dead function is the *only* place that would have supplied them. This is
  not a template guard doing its job — it is a wiring gap the `is defined` guards
  silently absorb.
- **Heuristic warnings are discarded.** `create_validator_function`
  (`heuristic_validator.py:73-76`) returns `result.errors` and drops
  `result.warnings`. "Plan doesn't cover all song sections"
  (`heuristic_validator.py:169-171`), bar-range mismatches against the detected song
  structure (`:234-241`), gaps between units (`:384-387`), and very-short sections
  (`:253-255`) are computed, logged nowhere the LLM can see, and thrown away. These
  are exactly the musical-alignment signals a planner could act on.
- **The judge rubric is meaningful but partly unread.** `JudgeVerdict` requires
  `overall_assessment` (2–4 sentences) and `score_breakdown` (named dimension
  scores) — grep-verified: **zero code consumers for either**. The judge is asked to
  produce a transparency artifact that is never surfaced, never logged as structured
  data, and never compared across iterations. `Issue.estimated_effort` and
  `Issue.suggested_action` are *required* fields on every issue with zero readers.

**Repair-loop cost ceiling.** Worst case per song on the shipped path, from the
configured attempt counts: macro planner 3 iterations × (planner ≤ 4 calls
[`macro_planner/specs.py:37`] + judge ≤ 6 calls [`:69`]) = 30; moving-head planner
3 × (≤ 4 [`moving_heads/specs.py:38`] + ≤ 4 [`:71`]) = 24; profile + lyrics ≤ 6.
**≈ 60 gpt-5.2/gpt-5-mini calls for one song** before any external failure — and per
P3-M-F each of those is up to 3 HTTP requests once the SDK's own retry layer is
counted, so ≈ 180 requests worst case. Per P3-M-D, most of the repair calls in that
total are **blind resamples**: on ONESHOT specs the model is never shown the output
it is being asked to fix, so those attempts buy far less than their price. Nothing
caps this: `token_budget` is unfed, and the repair loop's per-call cost is not
counted against iteration count. This is the pathological ceiling the phase brief
asked about, and it is real.

**Does the loop deliver value proportional to complexity?** From code evidence,
independent of Stage 2's outcome skepticism: partially, and less on the shipped path
than on the unshipped one. The genuinely valuable machinery — the five deterministic
auto-repair passes (`group_planner/orchestrator.py:450-483`: ID canonicalization
with `difflib` fuzzy matching, section-bound snapping, empty-plan dropping,
sequenced-window conflict dropping, same-target spacing sanitization) — lives
**entirely on the unreachable display path**. This corrects a discovery framing: the
"five deterministic auto-repair passes before judging" strength is not a property of
the shipped pipeline. The moving-heads path has **zero** auto-repair
(`heuristic_validator.py` only reports), and the macro path has exactly one
(`macro_planner/orchestrator.py:296-335`, section-ID canonicalization). So on the
path that ships, the loop is: generate → check → ask the model to try again with a
list of errors. That is the least sophisticated form of the pattern, and it is the
form that pays the full 60-call ceiling.

### 4.3 The agents, individually

**Audio profile — the Stage 2 claim, corrected in direction and worsened in
substance.** Stage 2 states the agent "re-derives values already printed into its own
prompt (`context.py:233-234`, `401-437` vs `user.j2:47-48,54`)". The **direction is
backwards**: `context.py:233-234` is the *original* deterministic derivation
(`mean_energy = sum(energies)/len(energies)`, `peak_energy = max(energies)`), written
into the shaped context at `:243-244`; `identify_characteristics` (`:401-437`) is
likewise the original derivation, written at `:245`; `user.j2:47-48,54` merely
*prints* those computed values. `context.py` re-derives nothing.

**But the underlying defect is real and larger than described.** The same prompt then
orders the model to reproduce them: `user.j2:106` — *"Calculate and report
mean_energy and peak_energy per section"*; `user.j2:105` and `developer.j2:27` —
*"Identify section characteristics … use standardized terms"*; and
`models.py:190,192,194` make all three **required**. Grep-verified: the only
non-test Python references to `.mean_energy`, `.peak_energy`, and `.characteristics`
are `context.py:243-245` writing the *input*. The pipeline computes three
deterministic values, spends tokens printing them, spends more tokens having a
temperature-0.4 frontier model restate them, and never reads the restatement. The
same pattern repeats for the energy curve: `user.j2:103-104` orders the model to
"preserve the exact timestamps … do not change timestamps" from
`compress_section_curve(..., points_per_section=8)` (`context.py:229`), and
`EnergyPoint.energy_0_1` has zero consumers repo-wide — with the added indignity
that `context.py:188` emits the key as `"energy"` while the schema requires
`energy_0_1`, so the model must rename the key it is copying.

`planner_hints` — the section the prompt labels *"⚠️ MOST IMPORTANT SECTION ⚠️"*
(`audio_profile/user.j2:132`) — **is** passed to the moving-head planner and judge
(`moving_heads/prompts/planner/user.j2:76-97`, `judge/user.j2:41-46`) but is
grep-verified absent from every macro-planner template and from all non-test Python.
Stage 2's claim as worded ("never passed to the macro planner") is exactly correct;
the broader reading that it is unused would not be.

**Lyrics — confirmed irreplaceable, and confirmed disconnected from the shipped
planner in a way Stage 2 did not identify.** The agent produces word-level cues
(`key_phrases[*].{text, timestamp_ms, emphasis, visual_hint}`, `story_beats[*]`).
Stage 2 says the only sink is a section-level template choice. It is worse:
`moving_heads/prompts/planner/user.j2:106-113` reads
`lyric_context.narrative_arc` and `lyric_context.key_moments[*].{section_id,
description}` — **neither field exists on `LyricContextModel`** (the real fields are
`mood_arc` at `lyrics/models.py:191` and `key_phrases` at `:212`; grep-verified:
`narrative_arc` and `key_moments` occur only at those four `.j2` lines and nowhere in
Python). Because the guards are `is defined and`, the blocks render as nothing,
silently. **The shipped moving-head planner receives zero lyric narrative context
even when lyrics are present**, despite `orchestrator.py:86` passing a fully
populated `LyricContextModel`. The lyric agent's output on the shipped path reaches
the planner only through the raw `{{ response_schema }}`-driven fields the templates
do reference — and reaches the renderer not at all.

**Macro planner + judge.** Confirmed: `MacroPlan` has **zero** references in
`packages/twinklr/core/sequencer/moving_heads/` (grep-verified — see §6/V2). The
macro judge's model is the confirmed bug: `MacroPlannerOrchestrator.__init__`
(`orchestrator.py:79`) calls `get_judge_spec()` with no arguments, and
`macro_planner/specs.py:44` defaults `model="gpt-5.2"`. `MacroPlannerStage`
(`stage.py:100`) does not pass a `judge_spec`. `AgentOrchestrationConfig.judge_agent`
(`config/models.py:108`) is grep-verified to have **no reader anywhere**. The
config field exists, is documented, is settable, and is inert.

The contrast is instructive: `MovingHeadStage` *does* read
`context.job_config.agent.max_iterations` (`moving_heads/stage.py:169-172`), so
`AgentOrchestrationConfig` is partly live.

**REVISED AT VERIFICATION — dead-member list corrected.** The author's original list
named `planner_agent`, which **does not exist**; the real field is `plan_agent`
(`config/models.py:107`). The verified dead members of
`AgentOrchestrationConfig` are: `judge_agent` (`:108`, P3-F2), `token_budget`
(`:84`) and `enforce_token_budget` (`:88`) (P3-F6), `token_buffer_pct` (`:90`),
`success_threshold` (`:100`, P3-M-A), and the three unused per-agent configs
`implementation_agent` / `refinement_agent` / `plan_agent` (the last reaching only a
fraction of invocations per P1-F15 — count that fact once, in phase 1). And
`max_iterations`, the one field that *is* read, accepts a documented value that
crashes (P3-M-B). This is a class where some fields work, some silently do not, and
one actively fails — the worst configuration failure mode, because it defeats the
user's ability to reason about the file at all.

**Moving-head planner.** `template_descriptions` are built from the registry
(`moving_heads/stage.py:231-242`) including `recommended_sections`, carried in
`TemplateDescription`, serialized into `for_prompt()["template_descriptions"]`, and
then — grep-verified: **`recommended_sections` appears in zero `.j2` files anywhere
in the repository** — never rendered. `user.j2:47` emits `description`,
`energy_range`, and `tags` only. This independently confirms Stage 2 §4's central
deterministic-selector observation from the agents side.

### 4.4 Prompt-injection surface (trust-boundary analysis)

`sanitize.py` provides one function, `sanitize_metadata_field` (strip
non-printables, truncate to 200 chars), with **exactly three call sites**
repo-wide (grep-verified): `audio/profile/context.py:62` (`audio_path`) and
`moving_heads/orchestrator.py:67-68` (`song_title`, `song_artist`). Everything else
is unsanitized. Rendering is `autoescape=False` (`renderer.py:32-37`) — correct for
plaintext prompts, but it means there is no output-side neutralization either.

**The load-bearing injection path**, with exact hops:

1. **Ingress**: raw lyric text from an embedded tag, LRCLib, or Genius —
   fully third-party-controlled — enters at `audio/lyrics/context.py:45`
   (`bundle.lyrics.text`), `:47` (word list), `:52` (phrases).
2. **Hop 1**: rendered verbatim into `audio/lyrics/prompts/lyrics/user.j2:38`
   (inside a fenced block), `:47`, `:62`. An attacker-authored `.lrc` can therefore
   place arbitrary instruction text, including newlines, into the lyrics agent's user
   message.
3. **Hop 2**: the lyrics agent's own output (`key_phrases[*].text` — which the prompt
   instructs it to quote verbatim — plus LLM-authored `visual_hint`,
   `story_beats[*].description`) is re-rendered into
   `macro_planner/prompts/planner/user.j2:114-115` and
   `group_planner/prompts/planner/user.j2:171`.
4. **Hop 3**: on the display path, `request_extractor.py:154` builds
   `f'Lyric: "{phrase.text}" [{phrase.emphasis}] — {phrase.visual_hint}'` into
   `scene_context`, which lands at
   `assets/prompts/asset_prompt_enricher/user.j2:100`.
5. **Terminus**: the enricher's `EnrichedPrompt.prompt` is sent to the OpenAI
   **Images API** (`assets/generator.py:222` → `image_client.py:180`).

So untrusted third-party text crosses four LLM boundaries with zero sanitization at
any hop and terminates in a paid image-generation call whose "CRITICAL RULES"
(`asset_prompt_enricher/system.j2:17-24`) the injected content is positioned to
override. The display path is unreachable today, which caps the *current* severity —
but the first two hops are on the shipped path and are enough to steer the macro
planner.

Secondary untrusted sources, all unsanitized: ID3/MusicBrainz tags reaching
`macro_planner/planner/user.j2:8,9,12,13` (laundered through the profile agent);
xLights layout group names and tags — user-authored free text — reaching
`macro_planner/planner/user.j2:141-143`, `group_planner/planner/user.j2:73,75`, and
`moving_heads/planner/user.j2:41`; and corpus-mined FE recipe names reaching
`group_planner/planner/developer.j2:156-158`.

`sanitize_metadata_field` is also too weak for what it does cover.
**REVISED AT VERIFICATION — the mechanism was stated inverted.** Python's
`str.isprintable()` returns `False` for `\n` and `\t`, so the filter would strip
them; `sanitize.py:23` then **explicitly re-admits both**:

```python
cleaned = "".join(c for c in cleaned if c.isprintable() or c in ("\n", "\t"))
```

The comment on the line above reads "Remove control characters (keep printable +
newlines + tabs)" — so the newline pass-through is deliberate, not an oversight in
the predicate. The conclusion is unchanged and now better supported: a 200-character
multi-line instruction block survives the *sanitized* path intact, by design.

**Realistic impact.** The worst outcome is a steered plan — a template/preset
selection the user did not intend, or a fabricated "issue" the judge accepts. It is
not remote code execution, and the sandboxed Jinja environment prevents template
escape. But it is unbounded influence over a paid, network-connected pipeline from a
file a user downloads, and there is no trust boundary drawn anywhere in the design.

### 4.5 Provider abstraction

Weakest layer in the phase. Four concrete problems.

**Two OpenAI clients in one provider.** `OpenAIProvider.__init__` constructs both an
`AsyncOpenAI` (`openai.py:67`) and a `core/api/llm/openai/client.OpenAIClient`
(`:68`), with independent retry and timeout policies. The async path retries 3× with
`0.5 * 2**attempt` backoff (`:312-320`); the sync path uses whatever the other client
implements. The sync methods (`generate_json`, `generate_json_with_conversation`) are
grep-verified unreachable from the agent runner, which is async-only — so the second
client is a permanently instantiated, never-exercised dependency that doubles the
retry surface a reader has to reason about.

**Conversation windowing duplicated.** `_window_messages` exists at
`openai.py:225-254` and again at `anthropic.py:131` with the docstring "mirrors the
OpenAI provider". Two implementations of the same 2-exchange sliding window.

**Temperature is silently dropped for "mini" models.** `openai.py:302-303`:
`is_mini_model = "mini" in model.lower()`; if true, `temperature` is not sent. So
`mh_judge`'s carefully-chosen `temperature=0.3` (`moving_heads/specs.py:46`) and
the section judge's and the asset enricher's `0.6` are all silently discarded — a
substring match on the model name changes sampling behavior with no log line. This
also means the Stage 6 retarget to `gpt-5.6-luna` would silently *re-enable*
temperature for those agents.

**Assistant turns are re-serialized, not echoed.** Both providers append
`json.dumps(response.content)` as the assistant message
(`openai.py:449-451`, `anthropic.py:467`), not the model's original text. Key order,
whitespace, and any non-JSON preamble are lost, so the conversational history the
model sees is not what it produced.

**Anthropic maturity — and it is reachable, contrary to the author's original
claim.** 533 lines, structurally parallel, with `Any`-typed response handling
(`_extract_token_usage`, `_parse_response_text` at `:180`, `:201`) and a hardcoded
`max_tokens=4096` default (`:260`, `:390`) that would truncate the larger plans.

**REVISED AT VERIFICATION — the CLI-gate claim is rejected.** `cli/main.py:158-162`
only checks that the `OPENAI_API_KEY` environment variable is **non-empty**:

```python
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    console.print("[red]ERROR: OPENAI_API_KEY environment variable not set[/red]")
```

It never inspects or selects the provider. Provider choice comes from
`AppConfig.llm_provider` via `create_llm_provider` (`factory.py:24-39`), so a
`config.json` setting `llm_provider: "anthropic"` **runs end-to-end** as long as some
value is present in `OPENAI_API_KEY` — the environment check and the provider
selection are entirely independent. The Anthropic path is therefore
**latent-reachable, not dead**, and its defects (including P3-M-I below) are
reachable by configuration alone.

### 4.6 Pydantic schema design vs strict structured outputs (M2 readiness)

Assessed against modernization.md M2's stated constraints (all fields required,
`additionalProperties: false`, object root, no `allOf`, ≤5 000 properties, ≤10
nesting levels, ≤1 000 enum values).

**Favorable**: every response model has an object root; most already use
`extra="forbid"`; the categorical enums are small (well under 1 000 values); nesting
is ~4–5 levels deep at worst (`MacroPlan → layering_plan → layers[] →
target_selector → roles[]`), inside the limit.

**Blocking**: the models lean heavily on optionality and defaults —
`PlanSection.segments`, `preset_id`, `modifiers`, `transition_in/out` are all
optional; `default_factory=list` appears throughout; `MacroPlan.asset_requirements`
and `SectionCoordinationPlan.deviations` default to empty. Strict mode requires all
of these to become `X | null` with the model obliged to emit them explicitly. That is
mechanical but touches essentially every planner model.

**The genuinely awkward one**: `PlanSection` enforces "exactly one of `template_id`
or `segments`" through a validator plus a heuristic check
(`heuristic_validator.py:219-228`). Strict JSON Schema cannot express that
constraint, and a top-level union is disallowed. Migration would need either a
discriminated union under a `kind` field or acceptance that the either/or invariant
stays a post-validation check — in which case some of M2's promised retry-surface
reduction does not materialize for this model.

**The strongest argument for M2 is not the retry loop — it is the 20 unconsumed
fields.** Strict mode forces a schema author to declare every field required, which
would make it immediately obvious that the system is demanding
`Issue.estimated_effort`, `Issue.suggested_action`, `JudgeVerdict.overall_assessment`,
and `JudgeVerdict.score_breakdown` from every judge call with no reader. The
migration is an opportunity to delete, not merely to re-encode.

**Related, and independent of M2**: `schema_utils.get_json_schema_example` is called
with no `exclude_fields` by any caller (grep-verified), so framework-populated fields
appear in the schema block even where the prompt explicitly forbids emitting them —
`audio_profile/developer.j2:98` ("DO NOT generate `provenance`"),
`lyrics/developer.j2:115-116`, and `SectionCoordinationPlan.start_ms/end_ms`
documented as "NOT produced by the LLM" (`group_plan.py:117-119`). The prompt and the
injected schema contradict each other at these points, and the schema is the more
authoritative-looking of the two.

### 4.7 Observability and cost accounting

`LLMCallLogger` is a well-designed protocol (`logging/protocol.py`) with async-file
and null implementations, wired through every orchestrator (grep-verified: 19 call
sites). `_build_logging_context` (`async_runner.py:229-311`) is thoughtful — it
records prompt sizes per role, catalog/group counts, and plan JSON sizes without
dumping payloads, and it explicitly solves the "flat variables produce 'No context
provided'" problem the docstring describes. Failures are swallowed by design
(`_safe_log_start`/`_safe_log_complete`) so logging can never break a run. This is
above the bar for a hobby-scale project.

**Cost accounting is not trustworthy, for two compounding reasons.** (1) The
shared-counter delta described in §4.1 — which the shipped `profile`+`lyrics` wave
already triggers. (2) `AgentResult.tokens_used` is the same delta, and
`IterationContext.add_tokens` sums it (`controller.py:340,407`) into
`mh_tokens`/`macro_tokens` metrics. Every token figure the system reports is derived
from differencing a mutable shared counter rather than from the per-call
`response.usage` the provider already parses correctly at `openai.py:337-359`.
**This blocks Stage 2's instrument-then-decide experiment**, which needs credible
per-arm cost and token numbers before any deterministic-vs-LLM comparison can mean
anything. Note also that reasoning tokens — the largest cost uncertainty in Stage 2
§6 — are inside `output_tokens` and therefore counted, but are not separated
anywhere, so the retarget to GPT-5.6 (which defaults `reasoning.effort=medium`)
would show up as an unexplained cost jump with no attribution.

`IssueRepository` deserves separate mention as the one cross-run learning mechanism
that is actually live: enabled by default (`controller.py:76`), it appends every
judge issue to `data/agent_analytics/{agent}_issues.jsonl` (`repository.py:124`) and
injects the top-N recurring categories into the next run's developer prompt
(`controller.py:313-324`). It has no size cap, no retention policy, and no
configuration path from `JobConfig` — the storage dir is an `IterationConfig` default
(`controller.py:80-83`) that no orchestrator overrides. It grows without bound in a
gitignored directory.

### 4.8 The assets package (first read in this review)

Nine modules, ~2 500 LOC, coherent internally, and **unreachable from any shipped
entry point**. `AssetCreationStage` is constructed at exactly one site
(`pipeline/definitions/display.py:167-178`) behind `enable_assets: bool = False`
(`display.py:56`), and the only non-test caller of `build_display_pipeline` passes
`enable_assets=False` (`scripts/demo_sequencer_pipeline.py:565`). The CLI imports
only `build_moving_heads_pipeline` (`cli/main.py:19`).

**Correction to discovery §6's spend framing.** The reachable paid path today is not
the stage — it is `scripts/demo_asset_pipeline.py`, which bypasses the stage entirely,
imports the generator/client directly (`:31-47`), and constructs a real `AsyncOpenAI`
under `--live` (`:678`, `:776-778`). That script, not the pipeline, is what an
unwary Stage 4 run could trip.

**Spend risk if `enable_assets=True` were set.** `gpt-image-1.5`, `n=1` hardcoded
(`image_client.py:183`), `size` always resolving to `1024x1024` because
`AssetSpec.width/height` default to 1024 and no caller overrides
(`models.py:129-130`), no `quality` parameter sent at all. **No cost cap, no budget
check, no dry-run, no confirmation gate** — grep-verified. Image count is
**unbounded by construction**: narrative specs are one image per
`GroupPlanSet.narrative_assets` directive, and that list has no `max_length`
(`group_plan.py:137`) — an LLM-authored list length directly determines paid API
calls. `Semaphore(5)` (`stage.py:197`) limits rate, not total. Two-tier caching
(spec-id pre-enrichment at `catalog.py:119`, prompt-hash post-enrichment at `:18`) is
the only brake, and it has three holes. **REVISED AT VERIFICATION** — the author's
first hole (FAILED entries excluded from reuse at `models.py:326,350`, so a
post-billing validation failure at `generator.py:239-248` is re-billed) is
**withdrawn**: `_process_image_bytes` resizes the decoded image to the requested
dimensions *before* `_validate_image` compares them, making that check tautological,
so the post-billing FAILED path it assumed does not arise. The two surviving holes,
plus the one the verifier added: the catalog is saved only at the very end
(`stage.py:216`), so a mid-run failure discards the record of everything already paid
for; nothing checks `output_path.exists()` before calling the API; and the catalog —
the sole record of paid work — is written non-atomically with all load errors
swallowed (**P3-M-L**, `catalog.py:61-66,71-84`), so a torn write or corrupt file
silently triggers full regeneration.

**Path traversal.** `_build_output_path` (`generator.py:52-62`) constructs the
filename from `spec.motif_id or spec.spec_id` with a single transformation —
`.replace(" ", "_").lower()` (`:55`). `/`, `..`, and leading `/` all pass through.
Both feeders are LLM-authored: `motif_id` from `section.motif_ids` and
`placement.param_overrides["motif_hint"]` (`request_extractor.py:104-109`), and
`spec_id` from `directive.directive_id`, constrained only by `min_length=1`
(`group_plan.py:48`). `mkdir(parents=True, exist_ok=True)` then creates whatever that
resolves to (`image_client.py:105`). A planner emitting
`directive_id="../../../../etc/cron.d/x"` writes a PNG outside the assets tree.
Unreachable today; a latent security defect the moment the flag flips.

**Provider-type confusion.** `stage._build_image_client` (`:273-282`) reaches into
`provider._async_client` — a private attribute — and guards with
`hasattr(provider, "_async_client")`, which is **also true for `AnthropicProvider`**
(`anthropic.py:71`). Under an Anthropic-configured session it would hand an
`AsyncAnthropic` to `OpenAIImageClient` and fail at call time with a non-retryable
`AttributeError`, after the enrichment calls were already paid for.

**Dead surface within the package**: `AssetSpec.matched_template_id`,
`text_timing_ms`, `token_budget`, `format`; `CatalogEntry.embedding`;
`AssetCategory.{IMAGE_PLATE, TEXT_LYRIC, SHADER}` (never produced; `SHADER` would hit
the "Unsupported category" FAILED branch at `generator.py:165-174`); and
`enrich_spec`'s `builtin_prompt` parameter, never passed a non-`None` value by any
caller (`prompt_enricher.py:119,144`) — the entire builtin-template matching feature
is scaffolded and unimplemented. Zero TODO/FIXME markers in the package.

Also: `ImageResult.file_path` and `CatalogEntry.file_path` are documented as
"relative to assets/ root" (`models.py:189,212`) but written as absolute paths
(`image_client.py:109`, `generator.py:253`), so `check_reuse`'s
`Path(entry.file_path).exists()` (`catalog.py:106`) misses every cache hit if the
artifacts tree moves — a silent full-regeneration (and full re-bill) trigger.

### 4.9 Confirmed-dead modules in scope

`token_budget_manager.py::TokenBudgetManager` (274 lines): grep-verified **zero
importers**, not even the package `__init__`. Fully dead.
`state_machine.py::OrchestrationStateMachine` (414 lines): imported only for
re-export in `agents/__init__.py:48-51`; no functional caller. Both confirm
discovery §5. Note that `AgentSpec.token_budget` is a *third*, independent dead
token-budget surface: it is set by every spec factory, is part of the frozen public
model, and is grep-verified never read by `async_runner.py`. Three separate
token-budget mechanisms exist; exactly one (`IterationConfig.token_budget`) is
functional, and it is never fed.

## 5. Tests & validation assessment

**Counts corrected at verification**: 88 test files under `tests/unit/agents/` (90
Python files, of which 2 are conftests), 119 including integration. 23 use
`MagicMock`/`AsyncMock`/`patch`; the remaining ~65 test pure Pydantic models,
validators, and context-shaping functions, which is appropriate and reasonably done.

**REVISED AT VERIFICATION** — the author's original "there is no `conftest.py` under
`tests/unit/agents/`" is wrong: **two exist**, at
`tests/unit/agents/sequencer/group_planner/conftest.py` and
`tests/unit/agents/sequencer/macro_planner/conftest.py`. The substantive point
survives — both are planner-specific, neither provides a reusable LLM fake, and
there is no package-level `conftest.py` at `tests/unit/agents/`. Each of the 23
mocking files still constructs its own provider double.

The one place this is done well is `tests/unit/agents/shared/judge/
test_controller.py`, which drives `StandardIterationController` with a fake provider
and is the only test that exercises the iteration loop as a loop. Nothing tests the
runner's repair loop against a provider that returns *progressively repaired* JSON —
and per P3-M-D that question now has a structural answer rather than an open one:
for ONESHOT agents repair feedback **cannot** work, because the model is never shown
its failing output.

The asset tests (9 modules, 2 267 lines) are notably better isolated than the
average here: grep-verified that no test constructs a real `AsyncOpenAI`, and the
`_create_openai_client` indirection (`stage.py:285-289`) exists specifically to make
that impossible. Whoever wrote that package took paid-call safety seriously.

**What the tests cannot catch, by construction**: none of the four defects with the
largest behavioral impact — dead few-shot examples, the unwired
`build_judge_variables`, the nonexistent `lyric_context.narrative_arc` field, and the
20 dead schema fields — is detectable by any test in the current suite, because
all four are silent successes. `StrictUndefined` does not fire on `{% if x is defined
%}`, an unused variable raises nothing, and an unread model field validates fine. A
single test that renders every pack against a fully-populated context and asserts on
the *rendered output* would have caught the first three.

Stage 4 should additionally verify: whether `gpt-5.6-*` accepts `json_object` mode at
all (M2's open question — this phase owns the call site at `openai.py:298`), and
whether any of the 4 reported known failures live in this package.

## 6. Critical assessment — should this subsystem exist in its current form?

**No, not in this form.** But the reason is narrower than "the LLM isn't
load-bearing", and this phase's evidence sharpens rather than simply endorses
Stage 2.

The framework itself — one runner, one spec model, schema/taxonomy auto-injection,
one iteration controller, verdict enforcement — is competent, coherent engineering.
If Twinklr needed a multi-agent LLM layer, this is a credible one. The problem is
everything hanging off it. **Of ~50 solicited schema fields, 20 have no reader at all
and a further 21 exist only to be re-serialized into another model's prompt** — so
roughly four fifths of what the models produce never reaches deterministic code. One
of the two conversational agents cannot see the lyric context the code carefully
assembles for it; the judge cannot see its own history; the few-shot examples never
ship; the ONESHOT repair loop never shows the model what it got wrong; and the
transparency artifacts (`score_breakdown`, `overall_assessment`) exist only to be
discarded. The apparatus is elaborate and the information channel through it is
nearly closed — which is Stage 2's thesis, independently reached from the agent side.

**Note on the corrected numbers**: the verification-revised 20-dead figure is *less*
damning than the author's original 33, but the prompt-only tier it reclassifies into
does not rescue the design — a field that exists solely to be pasted into the next
model's prompt is still a field no deterministic consumer depends on. The conclusion
holds on the corrected evidence.

**Engaging Stage 2's per-agent verdicts:**

- **Audio profile → REPLACE with deterministic code.** *Agree, and strengthen.*
  Three required fields are LLM-laundered copies of values the pipeline already
  computed; the energy curve is a verbatim echo with a key rename; and every
  field that is *not* an echo (`creative_guidance.*`, `planner_hints.*`) is
  prompt-only — it exists to be re-serialized into another model's prompt.
  `recommended_asset_usage` is solicited and grep-verified absent from both code and
  templates. The one genuinely useful thing this agent does — turning structure and
  energy into `planner_hints` for the MH planner — is a paragraph of text a
  rules engine can produce from the same inputs.
- **Lyrics → KEEP (currently wasted).** *Agree, and worsen.* Stage 2 says the output
  is thrown away at the renderer. On the shipped path it is thrown away one stage
  *earlier*: the MH planner template reads two fields that do not exist
  (`user.j2:106-113`), so the planner never sees narrative context at all. This is a
  ~5-line template fix that would materially change what the shipped planner knows,
  and it should be tested before any conclusion is drawn about whether lyric
  interpretation adds value — the experiment Stage 2 proposes would otherwise measure
  a broken wire.
- **Macro planner + judge → CUT from the moving-heads path.** *Agree on evidence,
  with one refinement (see V2 below).* Prose-only influence confirmed; 2–6 gpt-5.2
  calls; and the judge runs at frontier price because of a wiring bug rather than a
  decision.
- **MH planner → deterministic-by-default with LLM as A/B arm.** *Refine.* The
  agents-side evidence supports this, and adds the specific reason the deterministic
  arm is currently favored by accident: `recommended_sections` — the field that makes
  the template-selection join exact — is loaded, carried, serialized, and
  grep-verified never rendered into any prompt. The LLM is being asked to make a
  choice while being denied the column that decides it. Before running the A/B, that
  field should be exposed; otherwise the LLM arm is being handicapped by a template
  bug, not evaluated.
- **MH judge → CUT until evidence justifies.** *Agree, and add a mechanism reason.*
  The judge is fed planner variables, has no memory of its prior verdicts within a
  run, and produces two required narrative fields nobody reads. Whatever value an
  LLM critic could add, this configuration is not positioned to deliver it.

**What should exist instead.** The runner, spec, prompt loader, taxonomy injection,
and provider abstraction are worth keeping at roughly a quarter of their current
supporting weight. The judge/iteration controller is worth keeping *if* the loop is
first fixed (judge context, warning propagation, per-call token accounting) and then
measured — but it should not survive on the shipped path unmeasured for another
release. The assets package and the group/holistic planner chain belong with the
display pipeline's disposition, not with the shipped agent layer.

## 7. Comparison with simpler / modern alternatives

**Native structured outputs (M2)** replaces the client-side repair loop with
server-side enforcement. Per §4.6 this is a real refactor and does not fully solve
`PlanSection`'s either/or invariant — but it is the right direction, and its
underrated benefit is that it forces the 20 dead fields into visibility.

**A single-call planner.** The macro→MH two-stage split costs 2–6 calls to produce
text that is re-serialized into the next prompt. Merging the two prompts into one
planner call would preserve all the information that currently flows (which is only
prose) at roughly half the calls, and would remove one judge entirely.

**A deterministic selector**, per Stage 2. From the agents side the strongest
supporting evidence is `recommended_sections`: the join key exists and is already
computed. The strongest *counter*-evidence is that nothing in this codebase records a
single human judgment about output quality, so "comparable choreography" has no
measurable meaning yet. Instrument before deciding, as Stage 2 concludes.

**A framework (LangGraph, the Agents SDK, DSPy).** Not recommended. Twinklr's runner
is ~560 lines and does exactly what is needed; a framework would add a dependency and
a migration without addressing any finding in this document. The problems here are
wiring and schema discipline, not orchestration primitives.

**Prompt-injection mitigation**: standard and cheap — delimit untrusted spans
explicitly, strip newlines from any interpolated third-party string, and treat the
lyric text as data rather than prose. No architectural change required.

## 8. Doc / context claims touching this phase

- `context/architecture/multi-agent-planning.md` documents a planner → heuristic →
  **LLM validator** → judge loop. The LLM-validator role does not exist in code
  (confirmed; also flagged in discovery §4). `context/current-state.md:23` repeats it.
- `memories/decisions/llm-plans-intent-renderer-implements-precision.md` — the
  principle is faithfully implemented in *schema design* (categorical enums,
  auto-injection, no numerics from the model) but its description of behavior matches
  only the display pipeline. On the shipped path the model emits no categorical
  intensity/duration enums that reach the renderer.
- `JobConfig.agent.token_budget` and `AgentOrchestrationConfig.judge_agent` are
  documented as live knobs and are inert. `max_iterations` on the same class *is*
  live (`moving_heads/stage.py:169-172`) — the class is partly working, which is
  worse for a user than uniformly dead.
- Seven `pack.yaml` files document required variables, iteration caps, and pack
  versions that nothing reads, with two versions recorded inverted against the
  provenance the orchestrators actually write.
- `docs/` claims about the multi-agent narrative should be re-checked against §4.2's
  finding that the shipped path has no auto-repair.

## 9. Architecture worth preserving

1. **Schema and taxonomy auto-injection** (`async_runner.py:93-97`,
   `schema_utils.py`, `taxonomy_utils.py`). Structurally prevents prompt/model drift.
   Keep as-is; add `exclude_fields` for framework-populated fields.
2. **Judge verdict enforcement** (`judge/models.py:98-120`). The LLM cannot emit a
   status inconsistent with its score. Small, correct, and the kind of guard most
   LLM-critic implementations omit. **QUALIFIED (P3-M-A)**: keep the *property*, not
   the implementation verbatim — the same validator hardcodes the 7.0/5.0 boundaries
   (`:132-137`) and is precisely what makes `success_threshold` inert. Preserving it
   unchanged forecloses configurable judge strictness, which Stage 2's ablation arms
   would need.
3. **`RevisionRequest.from_verdict`** (`judge/models.py:218-271`). Structured
   actions preferred over free text, priority derived from severity, strengths
   preserved as an explicit do-not-change list.
4. **The five deterministic auto-repair passes**
   (`group_planner/orchestrator.py:450-483`). Genuinely good engineering — fixing
   recurring LLM errors in code rather than spending an iteration asking. If the
   display path is cut, these should be salvaged as a pattern for whatever replaces
   the MH validator.
5. **`_build_logging_context`** (`async_runner.py:229-311`). Compact, useful,
   payload-free call logging with never-raise semantics.
6. **`AsyncAgentRunner` itself** as the LLM chokepoint **for the shipped pipeline**
   (qualified per P3-M-C — `recipe_builder`, FE normalization, and the image client
   bypass it) — one place to add structured outputs, one place to add sanitization,
   one place to fix token accounting.
7. **Asset test isolation** (`assets/stage.py:285-289` + the 9 test modules) — a
   deliberate seam that makes an accidental paid call in tests impossible.

## 10. CANDIDATE FINDINGS

Severity: CRITICAL / HIGH / MEDIUM / LOW / INFO. Confidence: CONFIRMED / HIGH /
MEDIUM / LOW. Relationship: ALIGNED_AND_SOUND / ALIGNED_BUT_FLAWED /
IMPLEMENTATION_DIVERGES_FROM_INTENT / INTENT_IS_INFERIOR_TO_IMPLEMENTATION /
BOTH_REQUIRE_RETHINKING / INSUFFICIENT_EVIDENCE.

### Stage-2 verification items

**P3-F1 — `MacroPlan` reaches the shipped renderer only as prompt prose**
`CRITICAL` · `CONFIRMED` · IMPLEMENTATION_DIVERGES_FROM_INTENT · **SIMPLIFY**
**VERDICT: CONFIRMS Stage 2 (V2), with one refinement.**
Grep-verified: zero occurrences of `MacroPlan` or `macro_plan` anywhere under
`packages/twinklr/core/sequencer/moving_heads/`. The only route is
`MovingHeadPlanningContext.macro_plan` → `for_prompt()` builds a list of dicts
(`agents/.../moving_heads/context.py:208-228,243`) → `build_planner_variables`
(`orchestrator.py:88`) → `planner/user.j2:129` and `judge/user.j2:51-59`. No import,
no state key, no threading. **Refinement — one indirect route does exist and Stage 2
did not name it:** `MovingHeadPlannerOrchestrator.get_cache_key` includes the full
serialized macro plan (`orchestrator.py:236-238`), so `MacroPlan` content
participates in the MH stage's cache identity. It changes *whether* a cached plan is
reused, never *what* is rendered. This strengthens rather than weakens the claim: the
macro planner's only non-prose effect on the shipped path is cache invalidation.

**P3-F2 — `AgentOrchestrationConfig.judge_agent` never wired; macro judge silently
runs gpt-5.2** `HIGH` · `CONFIRMED` · IMPLEMENTATION_DIVERGES_FROM_INTENT · **FIX**
**VERDICT: CONFIRMS Stage 2 (§6), with a scope correction.**
`config/models.py:108` defines `judge_agent: AgentConfig`; grep-verified **zero
readers anywhere**. `MacroPlannerOrchestrator.__init__:79` calls `get_judge_spec()`
with no arguments; `macro_planner/specs.py:44` defaults `model="gpt-5.2"`;
`macro_planner/stage.py:100` passes no `judge_spec`. **Correction to Stage 2's
wording** ("both orchestrators … so the macro judge silently runs gpt-5.2"): only the
*macro* judge is affected. `moving_heads/specs.py:46` defaults to `gpt-5-mini`
independently, so the MH judge does run on the cheap model. The bug is real and
CONFIRMED for the macro judge; the "both orchestrators" framing overstates the blast
radius by one agent. Cost impact: up to 3 judge calls per song at frontier price
instead of mini price.

**P3-F3 — audio-profile agent re-emits deterministically computed values**
`HIGH` · `CONFIRMED` · BOTH_REQUIRE_RETHINKING · **REPLACE**
**VERDICT: REFINES Stage 2 (V-agents).** Stage 2's *direction* is refuted:
`context.py:233-234` and `:401-437` are the original derivations, written into the
context at `:243-245`; `user.j2:47-48,54` prints them. `context.py` re-derives
nothing. **The underlying defect is confirmed and larger**: `user.j2:105-106` and
`developer.j2:27` instruct the model to reproduce `mean_energy`, `peak_energy`, and
`characteristics`; `models.py:190,192,194` make all three required; grep-verified
zero non-test readers of the emitted values. Same for the energy curve
(`user.j2:103-104`; `EnergyPoint.energy_0_1` — zero readers), with a key rename
(`context.py:188` emits `"energy"`, schema requires `energy_0_1`) the model must
perform on data it is copying.

**P3-F4 — `planner_hints` never reaches the macro planner**
`MEDIUM` · `CONFIRMED` · ALIGNED_BUT_FLAWED · **FIX**
**VERDICT: CONFIRMS Stage 2 as worded, with a scope note.** Grep-verified:
`planner_hints` appears in `moving_heads/prompts/planner/user.j2:76-97` and
`judge/user.j2:41-46`, and in **no** macro-planner template and no non-test Python.
So it does reach a downstream LLM — the MH planner — just not the macro planner
(which runs first). Any restatement of this finding must not generalize to "never
used".

**P3-F5 — lyrics agent's word-level cues have no renderer sink, and no planner sink
either** `HIGH` · `CONFIRMED` · IMPLEMENTATION_DIVERGES_FROM_INTENT · **FIX**
**VERDICT: REFINES Stage 2 (V-agents) — the defect is one stage earlier than
described.** `moving_heads/prompts/planner/user.j2:106-113` reads
`lyric_context.narrative_arc` and `lyric_context.key_moments[*].{section_id,
description}`. `LyricContextModel` has neither (`lyrics/models.py:191` is `mood_arc`;
`:212` is `key_phrases`). Grep-verified: both names occur only at those four `.j2`
lines, nowhere in Python. The `is defined and` guards make the blocks render as
nothing. `orchestrator.py:86` does pass a populated model. **The shipped moving-head
planner is blind to lyric narrative context.** This must be fixed before Stage 2's
resolving experiment, or the LLM arm is measured with a severed wire.

**P3-F6 — dead-configuration class: `token_budget` threading**
`MEDIUM` · `CONFIRMED` · ALIGNED_BUT_FLAWED · **FIX**
**VERDICT: CONFIRMS discovery (critic B2) and extends it.** Three independent
token-budget surfaces exist. (1) `IterationConfig.token_budget` — functional
(`controller.py:452-453`), never fed by any stage. (2)
`AgentOrchestrationConfig.{token_budget, enforce_token_budget}`
(`config/models.py:84,88`) — read only by the dead `TokenBudgetManager`. (3)
**`AgentSpec.token_budget`** (`spec.py:70`) — threaded from all four orchestrators
into every spec factory and grep-verified **never read by `async_runner.py`**. This
third surface is new to this review. Remediation is to keep exactly one and delete
the other two.

### Iteration loop and feedback

**P3-F7 — the entire `judge_context_builder` hook is dead, and its signature cannot
carry feedback** `HIGH` · `CONFIRMED` · IMPLEMENTATION_DIVERGES_FROM_INTENT · **FIX**
`moving_heads/orchestrator.py:97-138` defines `build_judge_variables`;
`__init__.py:22,50` exports it; grep-verified **no caller**. `run()` (`:309-317`)
omits `judge_context_builder`, so `controller.py:501-541` supplies planner vars +
`plan`. Consequence: `previous_feedback`/`previous_issues` are never set, so
`judge/user.j2:72-90` never renders and the judge has no memory of its own prior
verdicts across iterations of the same run.

**EXTENDED AT VERIFICATION — the remedy is larger than wiring one call.** (1) The
`judge_context_builder` parameter (`controller.py:270`) is grep-verified to have
**no caller anywhere**, not just in moving-heads: all three orchestrators
(`macro_planner/orchestrator.py:271-278`, `moving_heads/orchestrator.py:309-317`,
`group_planner/orchestrator.py:308-315`) call `controller.run()` without it. The
whole extension point is dead and *every* judge in the system runs on
`_prepare_judge_variables`. (2) The hook's signature is
`Callable[[TPlan, int], dict[str, Any]]` — plan and iteration number only, with **no
parameter through which prior verdicts, feedback, or issues could be passed**.
`IterationContext` holds that history (`controller.py:119-120`) and is never offered
to the builder. Wiring `build_judge_variables` in as-is would therefore still leave
the judge without its history; the signature must change first. This is a design
gap, not a missing argument.

**P3-F8 — heuristic warnings are computed and discarded**
`MEDIUM` · `CONFIRMED` · ALIGNED_BUT_FLAWED · **FIX**
`heuristic_validator.py:73-76` returns `result.errors` only. Section-coverage gaps
(`:169-171`), structure-mismatched bar ranges (`:234-241`), inter-unit gaps
(`:384-387`), and very-short sections (`:253-255`) never reach the planner or judge.
These are the musical-alignment signals most likely to improve output.

**P3-F9 — repair-loop cost ceiling is ~60 LLM calls per song, uncapped**
`MEDIUM` · `CONFIRMED` · ALIGNED_BUT_FLAWED · **FIX**
Macro 3 × (4 + 6) = 30 (`macro_planner/specs.py:37,69`); MH 3 × (4 + 4) = 24
(`moving_heads/specs.py:38,71`); profile + lyrics ≤ 6. No cap: the only ceiling
mechanism (`IterationConfig.token_budget`) is unfed (P3-F6), and repair attempts are
not counted against iterations.

**P3-F10 — the five auto-repair passes exist only on the unreachable display path**
`MEDIUM` · `CONFIRMED` · ALIGNED_BUT_FLAWED · **KEEP (salvage)**
`group_planner/orchestrator.py:450-483`. The shipped MH path has zero auto-repair
(`heuristic_validator.py` reports only); the macro path has one
(`macro_planner/orchestrator.py:296-335`). **This refines discovery §5's framing of
"five deterministic auto-repair passes" as a property of the live loop** — it is a
property of the loop that does not run.

**P3-F11 — ultra-short-section path bypasses heuristic errors, not just the judge**
`MEDIUM` · `CONFIRMED` · ALIGNED_BUT_FLAWED · **FIX** (display path)
`group_planner/orchestrator.py:381-402`: on validation failure the errors are logged
and the plan is accepted anyway ("better to have an imperfect pickup than a pipeline
failure"). Discovery described this as a judge bypass; it is a full validation bypass.
The rationale is defensible; the silence is not — the accepted errors never surface
in metrics or the stage result.

### Prompt / schema co-design

**P3-F12 — 20 solicited schema fields are genuinely dead**
`HIGH` · `CONFIRMED` · BOTH_REQUIRE_RETHINKING · **SIMPLIFY**
**VERDICT: CONFIRMS Stage 2's direction; the author's headline count is CORRECTED
DOWN at verification.**

**REVISED AT VERIFICATION — 20 dead, not 33 (and the author's own list held 50
field entries, itself a miscount).** The verified partition of those 50 is
**20 dead / 9 with real readers / 21 prompt-rendered**. The author's sweep failed in
one specific way: it grepped for each field *by name* and so missed fields that reach
a prompt inside a **whole-model `| tojson` dump**. Three such dumps exist
(grep-verified — these are the only whole-model dumps in any pack):

- `moving_heads/prompts/judge/user.j2:12` — `{{ plan | tojson(indent=2) }}` renders
  **every** `ChoreographyPlan` / `PlanSection` / `PlanSegment` field.
- `group_planner/prompts/section_judge/user.j2:93` — same for
  `SectionCoordinationPlan`, including `deviations` and every `Deviation` field.
- `group_planner/prompts/holistic_judge/user.j2:137` — same for the whole
  `GroupPlanSet`.

**(a) The 9 with real Python readers — the author was wrong to call these dead.**
All nine reach the evaluation report model or the CLI console. They are copy-only
and never influence the render, but "zero consumers" was the wrong claim:
`ChoreographyPlan.overall_strategy` (`cli/main.py:281`);
`PlanSection.section_role` (`reporting/evaluation/generator.py:68`);
`PlanSection.energy_level` (`generator.py:69`);
`PlanSection.transition_out` (`generator.py:77`);
`PlanSection.reasoning` (`generator.py:73`, `render.py:151-152`);
`PlanSegment.reasoning` (`generator.py:617`);
`PlanSection.modifiers` and `PlanSegment.modifiers`
(`generator.py:591,616`, `compliance.py:57`);
and **`MacroPlan.asset_requirements`** (`macro_planner/heuristics.py:324,492`).

**F12 ↔ F17 CONTRADICTION RESOLVED.** The author listed
`MacroPlan.asset_requirements` as having zero consumers here while P3-F17 cited
`heuristics.py:324,492` validating it — mutually exclusive claims in the same
document. **F17 is correct; F12's entry is withdrawn.** The field has a real reader.
The disposition is unchanged and now rests on a cleaner argument: the prompt forbids
emitting it (`macro_planner/planner/developer.j2:72-73`) while a heuristic validates
its contents — so the right remediation is deletion of the field *and* its validator,
not deletion of an unread field.

**(b) The 21 prompt-rendered.** Reached only by a downstream LLM prompt, never by
deterministic code — the same "prompt-only" tier the author described but did not
count. Composition: 8 `ChoreographyPlan`/`PlanSection`/`PlanSegment` fields via the
MH-judge dump; 7 `SectionCoordinationPlan`/`Deviation`/`NarrativeAssetDirective`
fields via the two group dumps; the 4 `MotifSpec` fields via `{{ motif }}` at
`holistic_judge/user.j2:114`; `GlobalStory.pacing_notes`
(`holistic_judge/user.j2:119`, `macro_planner/judge/user.j2:119`);
`LayerSpec.intensity_bias` (`group_planner/planner/user.j2:145`,
`macro_planner/judge/user.j2:130`); `SongIdentity.key`
(`macro_planner/planner/user.j2:12`); `LyricContextModel.lyric_density`
(`macro_planner/planner/user.j2:124`); and the audio-profile echo fields whose names
appear in their own soliciting prompt's input block
(`audio_profile/user.j2:47-48,54,96`).

**(c) The 20 genuinely dead** — no code reader, no prompt render, no whole-model
dump: `PalettePlan.transition_notes`; `LayeringPlan.strategy_notes`;
`LayerSpec.timing_driver`; `TargetSelector.coordination`;
`CorrectionResult.correction_notes`; `AudioProfileModel.{agent_id, schema_version}`;
`Structure.notes`; `EnergyProfile.{overall_mean, energy_confidence}`;
`EnergyPoint.energy_0_1`; `CreativeGuidance.recommended_asset_usage`;
`LyricContextModel.{vocal_coverage_pct, timed_word_coverage_pct, vocal_presence_pct}`;
`JudgeVerdict.{overall_assessment, score_breakdown}`;
`Issue.{estimated_effort, suggested_action, scope}`;
`HolisticEvaluation.{score_breakdown, recommendations}`.

**Residual uncertainty flagged for Stage 5**: the dead↔prompt-rendered boundary for
a handful of audio-profile fields turns on whether an echo in the *soliciting*
prompt's own input block counts as "rendered". The author's field-level sweep was
demonstrated unreliable, so the three bucket **counts** (20/9/21) carry the
verifier's authority; individual bucket assignments at that boundary do not.

Two entries remain worse than merely unread, and both survive the correction:
`Issue.estimated_effort` and `Issue.suggested_action` are **required** fields on
every judge issue with zero readers of any kind; and `PlanSection.modifiers` has a
*compliance checker* (`generator.py:591,616`, `compliance.py:57`) validating
modifiers against a render that never applied them — a check that can only pass
vacuously or fail spuriously.

**Methodological note for any re-run**: a by-name grep is insufficient on this
codebase. Field-consumption analysis must first enumerate whole-model
`model_dump()` / `| tojson` sites and treat every field of those models as
prompt-reachable.

**P3-F13 — few-shot examples never reach any model**
`MEDIUM` · `CONFIRMED` · IMPLEMENTATION_DIVERGES_FROM_INTENT · **FIX**
Two independent causes: `loader.py:86,201` looks only for `examples.jsonl`, so
`audio_profile/prompts/audio_profile/examples/example_{1,2}.json` are never opened
despite being listed in that pack's `pack.yaml`; and
`async_runner.py:452-457` rebuilds the conversational request from
`user_messages[-1]` only, dropping the example turns appended at `:221-222`. The only
two packs with an `examples.jsonl` (`macro_planner/planner`, `group_planner/planner`)
are both CONVERSATIONAL. The `group_planner` examples were verified schema-correct
against `SectionCoordinationPlan` — real authoring effort that has never shipped.

**P3-F14 — `recommended_sections` is loaded, carried, serialized, and never rendered**
`MEDIUM` · `CONFIRMED` · ALIGNED_BUT_FLAWED · **FIX**
`moving_heads/stage.py:238-240` populates it into `TemplateDescription`;
`context.py:233` serializes it; `planner/user.j2:47` emits only `description`,
`energy_range`, and `tags`. Grep-verified: `recommended_sections` appears in **zero
`.j2` files repo-wide**. Independently confirms Stage 2 §4 from the agents side and
is a precondition for any fair deterministic-vs-LLM comparison (see §6). Cross-phase:
phase 4 owns the template metadata itself.

**P3-F15 — `pack.yaml` is entirely unenforced, with inverted version provenance**
`LOW` · `CONFIRMED` · ALIGNED_BUT_FLAWED · **REMOVE**
Grep-verified: `pack.yaml` appears in zero `.py` files. `loader.py:161-212` hardcodes
the file list; only `system.j2` is required. Declared `variables.required`,
`metadata.max_iterations`, and `templates.*` are decorative. `lyrics/pack.yaml`
declares `pack_version: "2.0"` while `lyrics/orchestrator.py:181` writes `"1.0"`;
`audio_profile/pack.yaml` declares `"1.0"` while `profile/orchestrator.py:174` writes
`"2.0"` — inverted for both. Four packs have no `pack.yaml`. Confirms discovery.

**P3-F16 — prompts and the injected schema contradict each other on
framework-populated fields** `LOW` · `CONFIRMED` · ALIGNED_BUT_FLAWED · **FIX**
`schema_utils.get_json_schema_example` accepts `exclude_fields` but no caller passes
it (grep-verified), so `provenance`, `run_id`, `SectionCoordinationPlan.start_ms/
end_ms`, and `NarrativeAssetDirective.section_ids` appear in the injected schema while
`audio_profile/developer.j2:98`, `lyrics/developer.j2:115-116`, and
`group_plan.py:117-119` say not to emit them.

**P3-F17 — prompt constraints without schema backing, and schema limits the prompts
contradict** `LOW` · `CONFIRMED` · ALIGNED_BUT_FLAWED · **FIX**
`PlanSection.segments` allows `max_length=5` (`moving_heads/models.py:58-63`) while
four prompt lines say max 3 (`planner/developer.j2:55,131`). `MacroPlan.
asset_requirements` is validated by `heuristics.py:324,492` while
`macro_planner/planner/developer.j2:72-73` forbids emitting it at all.
`lyrics/developer.j2:12,13,18` states length limits (`mood_arc` 10+ chars,
`genre_markers` 0-5, `story_beats` 2-5) that the schema does not enforce
(`lyrics/models.py:191,195,207`). `group_planner/planner/system.j2:195` claims
`narrative_assets` is capped at 10 while `group_plan.py:137` has no `max_length` —
which is also the unbounded-spend driver in P3-F21.

### Security / trust boundary

**P3-F18 — untrusted lyric text crosses four LLM boundaries unsanitized and
terminates at a paid image API** `HIGH` · `CONFIRMED` · BOTH_REQUIRE_RETHINKING ·
**FIX**
Path, hop by hop: `audio/lyrics/context.py:45,47,52` (raw third-party lyric text) →
`lyrics/prompts/lyrics/user.j2:38,47,62` → `LyricContextModel.key_phrases[*].{text,
visual_hint}` → `macro_planner/planner/user.j2:114-115` **and**
`group_planner/planner/user.j2:171` → `assets/request_extractor.py:154` builds
`scene_context` → `asset_prompt_enricher/user.j2:100` → `EnrichedPrompt.prompt` →
`assets/generator.py:222` → `image_client.py:180` (OpenAI Images API). Zero
sanitization at any hop.

**SEVERITY RE-ANCHORED AT VERIFICATION.** HIGH is justified by **hops 1–2 alone**,
which are on the shipped moving-heads path: attacker-authored lyric text reaches the
lyrics agent verbatim and its output reaches the macro planner. Hops 3–5 require
`enable_assets=True` and are therefore latent, not live — the image-API terminus
makes the chain more vivid but is not what carries the severity. Any restatement
that leans on the paid-image terminus is over-claiming.

**MECHANISM CORRECTED**: `sanitize.py` has exactly three call sites repo-wide
(`profile/context.py:62`, `moving_heads/orchestrator.py:67-68`). Python's
`isprintable()` **rejects** `\n` and `\t`; `sanitize.py:23` then explicitly
re-admits both (`or c in ("\n", "\t")`, comment: "keep printable + newlines + tabs").
The author's original text had this inverted. The conclusion is unchanged and better
supported: multi-line injected text survives the sanitized path by design.

Secondary unsanitized sources: ID3/MusicBrainz tags
(`macro_planner/planner/user.j2:8,9,12,13`), xLights layout group names
(`user.j2:141-143`, `group_planner/planner/user.j2:73,75`,
`moving_heads/planner/user.j2:41`), corpus-mined recipe names
(`group_planner/planner/developer.j2:156-158`). Impact is planner/judge steering, not
code execution — Jinja is sandboxed — but it is unbounded influence over a paid
pipeline from a downloaded file.

**P3-F19 — asset filename construction permits path traversal from LLM-authored
strings** `MEDIUM` · `CONFIRMED` · ALIGNED_BUT_FLAWED · **FIX**
`generator.py:52-62`: `filename = spec.motif_id or spec.spec_id`, sanitized only by
`.replace(" ", "_").lower()` (`:55`); `/`, `..`, and leading `/` pass through, and
`mkdir(parents=True)` (`image_client.py:105`) creates the resolved path. Both feeders
are LLM-authored (`request_extractor.py:104-109,382`;
`Deviation`/`directive_id` constrained only by `min_length=1`, `group_plan.py:48`).
Latent — unreachable until `enable_assets=True`.

### Provider abstraction

**P3-F20 — two OpenAI clients with divergent retry policies; the sync one is
unreachable** `MEDIUM` · `CONFIRMED` · ALIGNED_BUT_FLAWED · **SIMPLIFY**
`openai.py:67-68` constructs both `AsyncOpenAI` and `core/api/llm/openai/client.
OpenAIClient`. The runner is async-only, so `generate_json` and
`generate_json_with_conversation` (`:88`, `:133`) are grep-verified unreachable from
any agent. Two retry/timeout policies, one exercised. Confirms discovery §5.

**P3-F21 — temperature silently dropped for any model whose name contains "mini"**
`MEDIUM` · `CONFIRMED` · ALIGNED_BUT_FLAWED · **FIX**
`openai.py:302-303`. `mh_judge` (`temperature=0.3`), `section_judge` (`0.3`), and
`asset_prompt_enricher` (`0.6`) all run at API default with no log line. Interacts
with M1: retargeting to `gpt-5.6-luna` would silently *re-enable* temperature for
those agents, changing behavior in a way the retarget would not predict.

**P3-F22 — conversation windowing duplicated; assistant turns re-serialized**
`LOW` · `CONFIRMED` · ALIGNED_BUT_FLAWED · **SIMPLIFY**
`_window_messages` duplicated at `openai.py:225-254` and `anthropic.py:131`. Both
providers append `json.dumps(response.content)` (`openai.py:449-451`,
`anthropic.py:467`) rather than the model's original text, so the history the model
sees is a re-encoding of its own output.

**P3-F23 — Anthropic provider is latent-reachable, untested, and carries a
turn-3 crash** `MEDIUM` · `CONFIRMED` · ALIGNED_BUT_FLAWED · **REMOVE or
KEEP-and-test**
**REVISED AT VERIFICATION — the author's unreachability claim is REJECTED, and the
severity raised from LOW accordingly.** The CLI does **not** gate provider selection:
`cli/main.py:158-162` only checks that the `OPENAI_API_KEY` environment variable is
non-empty and never inspects `llm_provider`. Provider choice comes independently from
`AppConfig.llm_provider` via `factory.py:24-39`, so a `config.json` with
`llm_provider: "anthropic"` **runs end-to-end** provided any value sits in
`OPENAI_API_KEY`. The path is reachable by configuration alone.

533 lines; `Any`-typed response handling (`:180`, `:201`); hardcoded
`max_tokens=4096` (`:260`, `:390`) that would truncate large plans. Never executed by
any test or entry point. Its latent defects — including **P3-M-I**, which crashes on
the third conversational turn — are consequently **latent-reachable, not dead**, and
a user following the config documentation would hit them.

### Cost, observability, structured outputs

**P3-F24 — per-call token accounting differences a shared mutable counter; the
shipped path is already wrong** `MEDIUM-HIGH` · `CONFIRMED` · ALIGNED_BUT_FLAWED ·
**FIX**
**REVISED AT VERIFICATION — severity raised from MEDIUM, and the author's
"currently correct on the shipped path" scoping DELETED as wrong.**
`async_runner.py:86` and `:120` snapshot `provider.get_token_usage()` across `await`
boundaries; the counter is process-global (`openai.py:73-74`) and shared by all
concurrent agents against one memoized provider. **The `profile` and `lyrics` stages
share a single executor wave under `asyncio.gather`**, so two agents interleave their
snapshots on the only production path — every per-stage token figure the shipped
pipeline reports is already wrong today. Independently confirms P1-F27 from the
runner side; count the underlying defect once across the two phases.

**This blocks Stage 2's instrument-then-decide experiment**, which cannot compare
per-arm cost without trustworthy numbers.

**Fix scope is larger than the author stated.** The correct per-call figure exists
(`openai.py:361-367` populates `LLMResponse.metadata.token_usage`) but
`_execute_with_repair_async` returns only `(response.content, repair_attempts)`
(`async_runner.py:344,350`), discarding it. The fix requires threading the
`LLMResponse`/`TokenUsage` out through the repair loop into both `AgentResult` and
`_safe_log_complete`, and summing across repair attempts. This review owns the runner
side; phase 1 owns executor/session; neither alone is sufficient. Reasoning tokens
are inside `output_tokens` but never separated, so the GPT-5.6 retarget would show an
unattributable cost jump.

**P3-F25 — no native structured outputs; client-side repair loop instead**
`MEDIUM` · `CONFIRMED` · INTENT_IS_INFERIOR_TO_IMPLEMENTATION · **MODERNIZE**
`openai.py:298`: `"text": {"format": {"type": "json_object"}}`. Per M2 this is a real
refactor, not a flag flip; per §4.6 `PlanSection`'s exactly-one-of invariant cannot be
expressed in strict JSON Schema, so some retry surface survives. Sequence with M1.
Its underrated benefit is forcing P3-F12's unconsumed fields into visibility.

**P3-F26 — `IssueRepository` cross-run learning is live, unbounded, and
unconfigurable** `LOW` · `CONFIRMED` · ALIGNED_BUT_FLAWED · **KEEP + FIX**
Enabled by default (`controller.py:76`), appends JSONL to
`data/agent_analytics/{agent}_issues.jsonl` (`repository.py:124`), injects top-N
categories into the developer prompt (`controller.py:313-324`). No size cap, no
retention, and its storage dir is an `IterationConfig` default (`:80-83`) no
orchestrator overrides. This is the one genuinely functioning cross-run learning
mechanism in the system and deserves to survive — with a cap and a config path.

**P3-F27 — LLM call logging is a strength**
`INFO` · `CONFIRMED` · ALIGNED_AND_SOUND · **KEEP**
`logging/protocol.py` + `async_file_logger.py`, wired at 19 non-test call sites.
`_build_logging_context` (`async_runner.py:229-311`) records per-role prompt sizes and
payload-size indicators without dumping content; `_safe_log_*` never raises.

### Assets package

**SPLIT AT VERIFICATION** — the author's single HIGH finding conflated a dormant-code
hygiene question with a reactivation safety gate. They have different severities,
different owners, and different timing, so they are now two findings.

**P3-F28a — assets subsystem is ~2 500 LOC of unreachable production code**
`LOW` · `CONFIRMED` · ALIGNED_BUT_FLAWED · **REMOVE or DEFER**
`AssetCreationStage` constructed only at `pipeline/definitions/display.py:167-178`
behind `enable_assets: bool = False` (`:56`); the only non-test
`build_display_pipeline` caller passes `False` (`scripts/demo_sequencer_pipeline.py:
565`); CLI imports only `build_moving_heads_pipeline` (`cli/main.py:19`). As dormant
code it carries maintenance and refactor tax only — hygiene, to be resolved with
phase 5's display-path disposition, not before.

**P3-F28b — the assets subsystem has no cost controls of any kind: a HIGH
reactivation gate** `HIGH` · `CONFIRMED` · ALIGNED_BUT_FLAWED · **FIX before any
`enable_assets=True`**
`gpt-image-1.5`, always 1024×1024 (`models.py:129-130`, `image_client.py:60-61`),
`n=1` hardcoded (`:183`), and **no cost cap, budget check, dry-run, or confirmation
gate** (grep-verified). Image count is bounded only by `GroupPlanSet.
narrative_assets`, which has no `max_length` (`group_plan.py:137`) — **an LLM-authored
list length directly determines the number of paid API calls**. `Semaphore(5)`
(`stage.py:197`) limits rate, not total. This is not a defect of dormant code; it is
the precondition that must be satisfied before the flag is ever flipped, and it
should be recorded as a gate in the Stage 8 roadmap rather than a cleanup item.

**RE-BILL MECHANISM CORRECTED.** The author claimed FAILED entries are excluded from
reuse (`models.py:326,350`) so post-billing validation failures
(`generator.py:239-248`) get re-billed. **That mechanism is rejected**: `_process_
image_bytes` resizes the decoded image to the requested dimensions before
`_validate_image` compares them, so the dimension check is tautological and the
post-billing FAILED path it depends on does not arise in practice. The **real**
re-bill risk is the catalog itself (**P3-M-L**): it is the sole record of paid work,
is written non-atomically, is saved only after all generation completes
(`stage.py:216`), and `load_catalog` swallows every parse error and silently starts
fresh (`catalog.py:61-66`). Any of those three — mid-run failure, torn write, or a
corrupt file — discards the record of everything already paid for and causes a full
regeneration on the next run. There is also no `output_path.exists()` short-circuit
before calling the API.

**P3-F29 — correction to discovery §6: the reachable paid image path is a script,
not the stage** `MEDIUM` · `CONFIRMED` · ALIGNED_BUT_FLAWED · **FIX (Stage 4 guard)**
`scripts/demo_asset_pipeline.py` bypasses the stage, imports the generator and client
directly (`:31-47`), and constructs a real `AsyncOpenAI` under `--live`
(`:678`, `:776-778`). Discovery §6 attributed the spend risk to
`image_client.py:180` reached via the pipeline; the pipeline route is gated off. Stage
4 must treat this script, not `enable_assets`, as the paid-call hazard.

**P3-F30 — assets stage reaches into a private provider attribute and can mis-type
the client** `LOW` · `CONFIRMED` · ALIGNED_BUT_FLAWED · **FIX**
`assets/stage.py:273-282` guards on `hasattr(provider, "_async_client")`, true for
both `OpenAIProvider` (`openai.py:67`) and `AnthropicProvider` (`anthropic.py:71`),
and would hand an `AsyncAnthropic` to `OpenAIImageClient`. `generator.py:246,262` also
reads `image_client._model`. Broad `except Exception` at `stage.py:273-282` downgrades
a credentials failure to `"No image client provided"` with 100% FAILED entries.

**P3-F31 — asset catalog stores absolute paths documented as relative**
`LOW` · `CONFIRMED` · ALIGNED_BUT_FLAWED · **FIX**
`models.py:189,212` document "relative to assets/ root"; `image_client.py:109`,
`generator.py:253`, `text_renderer.py:103` write `str(output_path)` (absolute), so
`catalog.py:106`'s existence check misses every cache hit if the tree moves —
silently triggering a full regeneration and re-bill.

**P3-F32 — unimplemented scaffolding inside assets**
`INFO` · `CONFIRMED` · ALIGNED_BUT_FLAWED · **REMOVE**
`AssetSpec.{matched_template_id, text_timing_ms, token_budget, format}`;
`CatalogEntry.embedding`; `AssetCategory.{IMAGE_PLATE, TEXT_LYRIC, SHADER}` (never
produced; `SHADER` would hit `generator.py:165-174`'s FAILED branch);
`enrich_spec(builtin_prompt=...)` never passed a non-`None` value
(`prompt_enricher.py:119,144`). Zero TODO markers — the scaffolding is undocumented
as incomplete.

### Dead modules

**P3-F33 — three token-budget mechanisms, one functional, none fed; two dead
modules** `LOW` · `CONFIRMED` · ALIGNED_BUT_FLAWED · **REMOVE**
`token_budget_manager.py::TokenBudgetManager` (274 lines): grep-verified zero
importers, not even the package `__init__`. `state_machine.py::
OrchestrationStateMachine` (414 lines): imported only for re-export
(`agents/__init__.py:48-51`), no functional caller. Confirms discovery §5. Combined
with P3-F6's three token-budget surfaces, ~690 lines are removable with no behavior
change.

### Tests

**P3-F34 — no shared LLM fake; the loop's most impactful defects are untestable by
construction** `MEDIUM` · `CONFIRMED` · ALIGNED_BUT_FLAWED · **FIX**
No `conftest.py` under `tests/unit/agents/`; 23 of 106 files build ad-hoc provider
doubles. Only `tests/unit/agents/shared/judge/test_controller.py` exercises the
iteration loop as a loop, and nothing tests the repair loop against progressively
repaired JSON. P3-F5, P3-F7, and P3-F13 are all silent successes that no assertion in
the current suite can observe. **One test that renders every pack against a fully
populated context and asserts on the rendered output would catch all three.**
Counter-note: the assets tests are the best-isolated in the tree (grep-verified: no
real `AsyncOpenAI` anywhere under `tests/`, enabled by the `_create_openai_client`
seam at `stage.py:285-289`) — that pattern should be generalized, not replaced.

### Strengths

**P3-F35 — schema and taxonomy auto-injection**
`INFO` · `CONFIRMED` · ALIGNED_AND_SOUND · **KEEP**
`async_runner.py:93-97` + `schema_utils.py` + `taxonomy_utils.py`. Zero hand-authored
schema duplicates found across 11 packs. Confirms discovery's strongest positive
signal; add `exclude_fields` per P3-F16.

**P3-F36 — judge verdict status enforcement and `RevisionRequest.from_verdict`**
`INFO` · `CONFIRMED` · ALIGNED_AND_SOUND · **KEEP (qualified)**
`judge/models.py:98-120` makes an inconsistent verdict unrepresentable;
`:218-271` builds structured revision requests preferring `targeted_actions` over
free text and preserving strengths as an explicit do-not-change list.

**QUALIFIED AT VERIFICATION (see P3-M-A).** The same validator that makes this a
strength is also what kills the `success_threshold` knob:
`enforce_status_matches_score` hardcodes the 7.0/5.0 boundaries
(`judge/models.py:132-137`), so no configured threshold can move them. The mechanism
is worth keeping, but it must be *reworked* rather than preserved verbatim if
threshold configurability is ever wanted — the guard and the dead knob are the same
line of code. Any Stage 8 item that proposes keeping this as-is while also making
strictness configurable is internally inconsistent.

### Verifier-added findings (adopted)

_Twelve findings the author's review missed, contributed by the Stage 7 verifier and
adopted here with the verifier's evidence. Four are in-scope material defects
(M-A..M-E); M-J/K/L are assets-package and therefore reactivation-gated behind
P3-F28b._

**P3-M-A — `success_threshold` is documented, fully threaded, and inert**
`HIGH` · `CONFIRMED` · IMPLEMENTATION_DIVERGES_FROM_INTENT · **FIX**
`AgentOrchestrationConfig.success_threshold` (`config/models.py:100`, default 70,
`ge=0 le=100`, "Minimum judge score to accept plan") threads correctly all the way to
`IterationConfig.approval_score_threshold` via each orchestrator's `min_pass_score`.
It then does nothing: the controller's decision reads **status only**
(`controller.py:431`, `if verdict.status == VerdictStatus.APPROVE`), and status is
force-reconciled to **hardcoded** 7.0/5.0 boundaries by
`JudgeVerdict._expected_status_for_score` (`judge/models.py:132-137`). The
threshold is compared against nothing. **A new member of the dead-config class**
(P3-F6, P7-M2) and the most deceptive one, because the plumbing is complete and
correct right up to the point of use. **Consequence for Stage 2**: an ablation arm
that varies judge strictness would compare two identical configurations and report a
null result that means nothing.

**P3-M-B — the documented `max_iterations=0` ("skip judge") crashes**
`MEDIUM-HIGH` · `CONFIRMED` · IMPLEMENTATION_DIVERGES_FROM_INTENT · **FIX**
`AgentOrchestrationConfig.max_iterations` (`config/models.py:80-82`) declares
`ge=0` with the description "Maximum judge/iterate loops (**0=skip judge**)". The
value validates there, is read by `MovingHeadStage` (`stage.py:169-172`), and is
passed into `IterationConfig.max_iterations`, which declares `ge=1`
(`controller.py:56`) — a `ValidationError` at construction. The one documented way to
turn the judge off is an actively failing value, not merely a no-op. Note this is the
config knob Stage 2 would most want for its macro-ablated arm.

**P3-M-C — "every model call goes through `AsyncAgentRunner`" is false repo-wide**
`MEDIUM` · `CONFIRMED` · ALIGNED_BUT_FLAWED · **FIX (documentation)**
Three surfaces bypass the runner:
`feature_engineering/normalization/llm_review.py:71` (`chat.completions.create`),
`core/api/llm/openai/client.py:355,589,682` (`responses.create`, reached by
`recipe_builder`), and `assets/stage.py:289` (`AsyncOpenAI()` for images). All are
off the shipped path, so the chokepoint property holds where it matters — but §2 and
§9's "single LLM chokepoint" must be scoped to the moving-heads pipeline. Applied
above.

**P3-M-D — ONESHOT schema repair never shows the model its failing output**
`HIGH` · `CONFIRMED` · BOTH_REQUIRE_RETHINKING · **FIX**
`_execute_with_repair_async` appends only the formatted validation errors as a new
user message (`async_runner.py:390-396`); the model's failing response is **never**
appended as an assistant turn. For CONVERSATIONAL agents the provider stores the
assistant turn itself (`openai.py:449-451`), so the model can see what it produced.
For **ONESHOT** agents there is no such store — so every repair attempt is a **blind
full-cost resample**: the model is told "fix these errors" about output it cannot
see. This affects every judge (`mh_judge` ≤3, `macro_judge` ≤5), the audio-profile
and lyrics agents, and the holistic corrector. **This answers §5's open question**
("does repair feedback actually work?") structurally rather than empirically: on
ONESHOT specs it cannot. It also materially changes P3-F9's cost ceiling — a large
share of those ~60 calls are uninformed retries.

**P3-M-E — failed LLM calls produce no log record and retain full prompts**
`HIGH` · `CONFIRMED` · ALIGNED_BUT_FLAWED · **FIX**
`run()` calls `_safe_log_start` (`async_runner.py:106`) to open a call record, but
all three failure branches (`:154`, `:169`, `:188`) return an `AgentResult` **without
calling `_safe_log_complete`**. Every failed call therefore leaves a dangling open
record with no outcome, no token figures, and no error text — exactly the calls an
operator most needs to inspect, and exactly the ones Stage 4 would need to diagnose a
model retarget. The `messages` list (full rendered prompts, plus one appended repair
message per attempt) also stays referenced for the lifetime of the call.

**P3-M-F — SDK and manual retry layers multiply to ≤9 requests per logical call**
`MEDIUM` · `CONFIRMED` · ALIGNED_BUT_FLAWED · **FIX**
`AsyncOpenAI(...)` is constructed without `max_retries` (`openai.py:67`), so the SDK
default of 2 retries (3 attempts) applies; `generate_json_async` then wraps its own
`max_attempts = 3` loop (`:312-320`). The layers compose multiplicatively: **up to 9
HTTP requests for one logical call**, with the manual backoff (`0.5 * 2**attempt`)
unaware of the SDK's. Compounds P3-F9's ceiling and P3-M-D's blind resamples.

**P3-M-G — unparseable JSON gets zero retries while schema violations get five, and
it kills the run** `MEDIUM` · `CONFIRMED` · BOTH_REQUIRE_RETHINKING · **FIX**
`json.JSONDecodeError` is converted to `LLMProviderError` inside the provider
(`openai.py:333-335`), which `run()` catches at `:154` and returns as an immediate
failure — bypassing the repair loop entirely. A *schema* violation of the same
response gets up to 5 repair attempts. The inversion is backwards: **truncated or
prose-wrapped JSON is the most common `json_object`-mode failure**, and it is the one
treated as unrecoverable. Because the pipeline is fail-fast, it aborts the whole run.

**P3-M-H — the provider's conversation store is never evicted**
`LOW` · `CONFIRMED` · ALIGNED_BUT_FLAWED · **FIX**
`self._conversations: dict[str, Conversation]` (`openai.py:77`) is written at `:154`
and `:435` and grep-verified never deleted, popped, or cleared — `reset_token_tracking`
(`:208-212`) resets counters only. Every conversational agent's full history persists
for the provider's lifetime. Bounded per process today; a leak in any long-lived or
batch usage.

**P3-M-I — Anthropic conversation windowing produces assistant-first message lists
the API rejects** `MEDIUM` · `CONFIRMED` · ALIGNED_BUT_FLAWED · **FIX**
`_window_messages` keeps `conversation[-max_msgs:]` with `max_msgs = window_size * 2
= 4` (`anthropic.py:153-159`). At request time on the third turn the user/assistant
list is `[u1,a1,u2,a2,u3]` (odd length 5); `[-4:]` drops `u1`, yielding
`[a1,u2,a2,u3]` — **starting with an assistant message**, which the Anthropic
Messages API rejects. Every conversational agent (both planners) would fail on its
third iteration. Latent-reachable via config per the corrected P3-F23. The OpenAI
provider shares the identical slicing logic (`openai.py:250-252`) but the Responses
API tolerates the shape.

**P3-M-J — asset enrichment `gather` without `return_exceptions` discards paid
sibling work** `HIGH` (assets, reactivation-gated) · `CONFIRMED` ·
ALIGNED_BUT_FLAWED · **FIX**
`asyncio.gather(*[_enrich_one(s) for s in image_specs_to_enrich])` (`stage.py:181`)
and the generation gather (`:209`) both omit `return_exceptions=True`, while
`enrich_spec` raises on any failure (`prompt_enricher.py:150`). One failure
propagates out, the stage returns `failure_result`, and **every sibling call already
paid for in that batch is discarded** — with no catalog write (P3-M-L), so the next
run repeats and re-bills all of it.

**P3-M-K — asset reuse keys collide across songs**
`HIGH` (assets, reactivation-gated) · `CONFIRMED` · ALIGNED_BUT_FLAWED · **FIX**
The pre-enrichment reuse key is `spec_id + width + height`
(`catalog.py:119-149`) and `spec_id` derives from motif/directive identifiers
(`request_extractor.py:213,382`) that carry **no song or run scope**. Two different
songs producing the same motif id therefore share a cached image. Combined with the
`.lower()`/space-folding filename collapse (P3-F19), one file can back several
logically distinct catalog entries.

**P3-M-L — the catalog is the sole record of paid work and is written unsafely**
`HIGH` (assets, reactivation-gated) · `CONFIRMED` · ALIGNED_BUT_FLAWED · **FIX**
`save_catalog` (`catalog.py:71-84`) does a direct `write_text` — no temp-file-plus-
rename, so a crash mid-write leaves a truncated JSON file. `load_catalog`
(`:42-67`) catches **every** exception and silently returns a fresh empty catalog on
any parse error. It is written once, after all generation (`stage.py:216`). Any of
mid-run failure, torn write, or corruption discards the record of all paid work and
triggers full regeneration. This is the correct mechanism behind P3-F28b's re-bill
risk, replacing the author's rejected dimension-validation story.

## 11. Unresolved questions & cross-phase dependencies

1. **Does the LLM arm improve output once the wires are fixed?** P3-F5 (planner blind
   to lyrics), P3-F7 (judge blind to its own history), and P3-F14
   (`recommended_sections` withheld) mean the current system is not a fair
   representative of "LLM-driven planning". Stage 2's resolving experiment should run
   *after* these three fixes, or its LLM arm measures a broken configuration. **Feeds
   Stage 5/8.** Verification adds three more preconditions the experiment design must
   absorb: P3-F24 (per-arm token figures are wrong today, so cost comparison is
   blocked), P3-M-A (a judge-strictness arm would compare identical configs), and
   P3-M-B (the documented `max_iterations=0` needed for a macro-ablated arm crashes).
   **The instrumentation Stage 2 wants to build first is itself blocked on four
   agent-layer fixes.**
2. **Does `gpt-5.6-*` accept `json_object` mode?** M2's open question; the call site
   is `openai.py:298`. Cheap Stage 4 live test; gates whether M1 can ship without M2.
3. **Are the two `pack_version` values the only inverted provenance?** Only two packs
   record a version at all; whether the LLM-call logs carry the wrong version for
   past runs is unverified.
4. **Phase 4 seam — template metadata.** P3-F14 (`recommended_sections` never
   rendered) and the discriminating power of `energy_range`/`recommended_sections`
   across the 37 templates are phase 4's to answer; this phase confirms only the
   agents-side non-consumption.
5. **Phase 1 seam — token race (P3-F24 / P1-F27 are the same defect).** Both phases
   confirmed it independently; **Stage 5 must count it once**. This phase owns the
   runner-side fix, which is not a one-liner: the `LLMResponse` must be threaded out
   through `_execute_with_repair_async` into `AgentResult` and
   `_safe_log_complete`. Phase 1 owns the executor/session shared provider. Neither
   fix alone is sufficient.
6. **Phase 5/6 seam — display path disposition.** P3-F10 (auto-repair passes),
   P3-F11 (ultra-short bypass), and P3-F28a/b (assets) all live on the display path.
   If phase 5 recommends cutting it, the auto-repair passes should be salvaged as a
   pattern before deletion. P3-F28b (absent cost controls) is a **gate**, not a
   cleanup item — it must be satisfied before any future `enable_assets=True`,
   independently of whether the display path survives.
7. **Phase 7 seam — `scripts/demo_asset_pipeline.py`.** P3-F29's paid-call hazard
   sits in phase 7's scripts inventory; phase 7 should carry the Stage 4 guard.
8. **Unquantified**: actual per-song token/latency/cost on the shipped path. No
   telemetry exists in the repo and P3-F24 means historical figures were already
   wrong on the shipped `profile`+`lyrics` wave. Stage 4 measurement is the only
   route, and it must follow the P3-F24 fix to mean anything.
9. **Dead-config class (P3-F2, F6, M-A, M-B) joins P7-M2 and P1-F15.** Four phases
   have now independently confirmed members of the same class. Stage 5 should
   consolidate into one finding with one remediation, not six — and record that the
   user guide cannot be trusted as a behavior description.
10. **Residual from P3-F12**: the dead↔prompt-rendered boundary for a few
    audio-profile fields is unsettled (see the finding). The three counts carry the
    verifier's authority; individual assignments at that boundary do not.

## 12. Phase verification status

**VERIFIED — 2026-08-13, opus critic (non-author), with security-reviewer input per
plan.md.** Outcome: **22 ACCEPTED, 12 REVISED, 12 verifier-added findings adopted
(P3-M-A..M-L), 0 REJECTED outright** (two sub-mechanisms were rejected and replaced:
F23's CLI-gate claim and F28's re-bill story). All required corrections are applied
in this revision and marked inline as "REVISED AT VERIFICATION". The condensed
verdict record is in `reviews/verification.md` §"Phase 3".

**Confirmed clean — 19 findings held verbatim**, including P3-F1 (CRITICAL,
prose-only `MacroPlan`). The two most load-bearing claims were rated airtight:

- **P3-F5** (planner blind to lyrics) — three independent locks: the `extra="forbid"`
  model, model-object passing, and the phantom field names appearing in exactly four
  `.j2` lines and no Python. The Lyric Context block renders exactly one line:
  "Has Lyrics: Yes".
- **P3-F13** (few-shot never delivered) — both bugs confirmed, and worse than the
  author stated: the LLM call logs assert a delivery that never happened.

**What the verification changed most.** The author's field-consumption sweep was the
weakest artifact (P3-F12: 33 → 20 dead, with a self-contradiction against P3-F17),
and two scope claims were affirmatively wrong in the *safe* direction — the token
race (P3-F24) and the Anthropic path (P3-F23) were both described as unreachable
when both are live or config-reachable. Both were corrected upward in severity. The
methodological lesson is recorded in P3-F12 for any re-run: by-name grep is
insufficient where whole-model `| tojson` dumps exist.

**Residual open items** carried into Stage 5, not blocking: the dead↔prompt-rendered
boundary for a few audio-profile fields (P3-F12), and the `json_object`-on-gpt-5.6
live probe (§11.2), which needs an API key and remains outstanding after Stage 4.
