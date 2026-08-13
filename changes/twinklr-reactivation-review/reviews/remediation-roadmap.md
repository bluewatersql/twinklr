# Remediation Roadmap (Stage 8) — appendix

> **SUPERSEDED AS THE PLAN (2026-08-13, same day):** the owner rejected this
> document's defect-class organization — correctly — as "version bumps and bug
> fixes" without a destination. The plan is now
> **[reactivation-proposal.md](reactivation-proposal.md)**, whose workstreams
> reference this document's item IDs (RM-x.y) for item-level evidence, dependencies,
> and sequencing traps, which remain valid. Note the owner's edit standing in
> RM-3.1: the default retarget is `gpt-5.6-sol` (quality axis) — reflected in the
> proposal's D6.

_Dependency-aware program derived from the normalized findings (findings.md) and the
sequencing constraints recorded during verification. Baseline `aa8d325`, authored
2026-08-13. Scores are Impact/Effort/Complexity/Risk on 1–5 (5 = highest). Priorities:
P0 reactivation blocker · P1 stabilization/architectural correction · P2 important
maintainability/modernization · P3 optimization/cleanup · P4 optional. **This review
authorizes none of the work below; items marked ⚖ additionally require an explicit
project decision because they overturn an accepted decision or change user-facing
behavior.**_

## Standing gates

- **RM-G1 (⚖ LICENSE)**: no LICENSE has ever existed. Until decided, nobody else may
  legally use, contribute to, or receive this software. Blocks any distribution-shaped
  goal; independent of all code work. I/E/C/R 5/1/1/1.
- **RM-G2 (⚖ vendor rights)**: before resuming corpus mining or distributing any
  `source="mined"` recipe, resolve source-package licenses. Prospective gate;
  provenance hooks already exist. 4/2/2/2.
- **RM-G3 (model deadlines)**: `gpt-image-1.5` retires 2026-12-01; `gpt-5-mini`
  2026-12-11. RM-3.1 must land before these dates on any path that keeps those calls.

## Stage 0 — Immediate blockers and baseline repair (P0; goal: a clean checkout passes its own gates)

| Item | What | Findings | Deps | I/E/C/R |
|---|---|---|---|---|
| RM-0.1 | mypy gate: rename the reused loop variable in `recipe_builder/admission.py` (runtime already correct) | P6-M3 | — | 4/1/1/1 |
| RM-0.2 | Test-suite structural repair: delete the 60 tests for nonexistent `scripts/build/*` tools (CC-2 class — rebuild from intent only if the tools are wanted); gate the 52 `data/templates`-dependent tests behind a marker/fixture-presence skip WITH a tracked minimal fixture set; vendor or pre-fetch the NLTK resource for offline runs | CC-2, CC-7, Stage 4 | — | 4/2/2/2 |
| RM-0.3 | Format/lint baseline: one `ruff format` + triaged `ruff check --fix` pass as its own commit; decide the config unification (root strict set applied to core — expect a wave, budget it) | P1-F20, Stage 4 | RM-0.2 | 3/2/2/2 |
| RM-0.4 | Minimal CI (check-only): install → `ruff format --check` → `ruff check` → `mypy` → `pytest` (+ version-consistency check across the 5 declaration sites). `make validate` stays local-only until a `git diff --exit-code` guard is added (pattern already exists in-file) | SF-7, P7-F6 | RM-0.1..0.3 | 5/2/2/1 |
| RM-0.5 | Packaging: adopt `uv_build` backend per package, delete the `find_packages("../..")` setup.py shims, fix `make build` paths; acceptance = non-empty wheels, no tree pollution | P1-F23, CC-2 | — | 3/2/2/1 |
| RM-0.6 | Onboarding truth: delete the `.env` "option 2" or wire `pydantic-settings` (single decision, one owner — resolves the P7-F1/P1-F3 remedy conflict); fix `make env-check`'s false ✓; fix the two `PipelineContext` docstring constructors | P7-F1, P1-M2 | — | 3/1/1/1 |

## Stage 1 — Correctness and stabilization of the shipped path (P1; goal: output represents design intent, and the system is measurable)

| Item | What | Findings | Deps | I/E/C/R |
|---|---|---|---|---|
| RM-1.0 | **Golden render harness FIRST**: wire the existing 587-LOC `.xsq` validator into CI + pin golden settings-strings for 2-3 fixture rigs; add the shutter-channel=6/17 emitted-bytes test (spec in verification.md); add one parse→export round-trip test | ST-7, CF-7, CC-7 | RM-0.4 | 5/2/2/1 |
| RM-1.1 | **Render-path repair campaign** (one branch, golden-diffed): F1 intensity plumbing + F1a data fill-in + M6 frequency-amplitude (MUST land together) + M1 dimmer floors + M2 BLACKOUT inversion + F9 calibration + F4/F5/F6 scheduler + M5 snap-back + F2/M3 single time-grid (spans agents context.py — the phase-3 half ships with it) | CF-1, CF-2, CF-6 | RM-1.0 | 5/4/4/3 |
| RM-1.2 | Channel-default policy: unwritten channels emit the fixture's declared defaults (`shutter_default=255` etc.) instead of zero-fill; then Stage-4-empirical xLights acceptance test (import into 2026.15; stamp update) | CF-7, M6 | RM-1.0 | 5/2/2/2 |
| RM-1.3 | Audio truth campaign: metadata client fix (BOTH clients + MB rate limiter in the same change — the latent-violation trap) + lyrics gating inversion + WhisperX vocal gate (after) vocals hop-length fix + builds merge + trim guard + beats/bar threading + HPSS logging/status + retire-or-wire the decorative validator + first ground-truth assertions (click track tempo/beats, known key) | SF-1/2/3, CC-3 | RM-0.4 | 4/3/3/2 |
| RM-1.4 | Instrumentation unblock (prereq for the Stage-2 experiment): token attribution fix (thread LLMResponse out; per-call usage) + wire-or-delete token budget + fix inert `success_threshold` + clamp/honor `max_iterations=0` + deterministic session-ID + cache-root anchoring + prompt-content hashing (ALL cache items in one change) + lyric wiring fix (CF-4) + few-shot delivery decision | CC-4, CC-5, CF-4, P3-M-A/M-B | RM-0.4 | 5/3/3/2 |
| RM-1.5 | Dead-config triage: for each CC-1 member — wire it, or delete field+docs. No third state. Acceptance: every documented knob has a test asserting behavioral effect | CC-1 | RM-1.1/1.3/1.4 | 4/3/2/2 |
| RM-1.6 | Evaluation enablement: restore the checkpoint writer (~10 lines, serializing today's PlanSection — historical artifacts are NOT replayable), bridge `eval-report` into the CLI, commit the first evaluation result | SF-4 | RM-1.1 | 5/2/2/1 |

## Stage 2 — Architectural decision (the experiment; P1; ⚖ throughout)

| Item | What | Findings | Deps | I/E/C/R |
|---|---|---|---|---|
| RM-2.1 | Build the deterministic selector arm (energy_range ∩ section energy + recommended_sections join + variety constraints — annotations verified discriminating); run the 3-arm comparison (deterministic / full LLM / macro-ablated) over N≥10 songs; harness scores + **blind human ranking**; record cost/latency/tokens per arm | CF-3, Stage 2 §4 | RM-1.1, RM-1.4, RM-1.6 | 5/3/3/2 |
| RM-2.2 ⚖ | Product-boundary decision from M6b options: `.xtiming`-only MVP (mapping-free, smallest deliverable — ST-8) vs minimal generate-fresh `.xsq` (+`.xmap`, manual or API-triggered import) vs direct `addEffect` injection. Prereq empirical test: bare-`.xsq` import without rgbeffects.xml | CF-5, M6b | RM-1.2 | 5/3/3/3 |
| RM-2.3 ⚖ | LLM-boundary decision from RM-2.1 results: (a) deterministic default + LLM opt-in, or (b) widen the channel (color/gobo/shutter template parameters — export layer needs zero changes; template layer ~300 LOC plumbing + data-first template loader before re-authoring 37 templates). Either way: cut macro planner + judges from the shipped path unless the experiment defends them; update the accepted decision record | CF-3, P4-V1 | RM-2.1 | 5/4/4/3 |

## Stage 3 — Modernization (P2; sequenced per modernization.md)

| Item | What | Deps | I/E/C/R |
|---|---|---|---|
| RM-3.1 | Model retarget (M1): `gpt-5.2→gpt-5.6-sol` default, judge→terra/luna, image→gpt-image-2; explicit `reasoning.effort` per role; consolidate the 29 hardcoded sites into (now-wired) config; **include the out-of-framework site** `normalization/llm_review.py`; deadlines per RM-G3 | RM-1.4 (config wiring), RM-1.5 | 4/2/2/2 |
| RM-3.2 | Structured outputs (M2): after a one-call `json_object`-on-5.6 probe; migrate to strict json_schema / `responses.parse` (model changes: all-required fields, no top-level unions); shrinks the repair loop to refusal/truncation | RM-3.1 | 4/3/3/2 |
| RM-3.3 | ML chain bump (M3): torch/torchaudio 2.8.x + whisperx 3.8.6 + pyannote 4.x (breakage risk concentrated in the orphaned diarization module — delete it first) + Python 3.12→3.13 ⚖ (update constraint memory) | RM-0.4 | 3/3/3/3 |
| RM-3.4 | Drop sqlite-vec extra (M7); defer openai-SDK 3.x and mypy 2.x as soak-then-adopt (M4/M5) | — | 2/1/1/1 |

## Stage 4 — Reliability/operability (P2)

| Item | What | Findings | I/E/C/R |
|---|---|---|---|
| RM-4.1 | Observability spine: error taxonomy for degradation (SKIPPED/FAILED surfaced to CLI output); failed-LLM-call logging; effect-fallback warnings into WriteResult; wave failure preserves sibling results | CC-3, P1-M1, P3-M-E, P5-M1 | 4/3/2/2 |
| RM-4.2 | Retry/limits rationalization: single retry policy (SDK max_retries explicit), JSON-parse failures get parity with schema failures, conversation-store eviction, httpx client lifecycle, prompt-injection hardening on shipped hops | CC-4/9, P3-M-F/G/H | 3/3/2/2 |

## Stage 5 — Cleanup and debt retirement (P3)

| Item | What | Deps | I/E/C/R |
|---|---|---|---|
| RM-5.1 | Duplication collapse: one OpenAI client, one configure_logging (delete dead `AppConfig.logging` or wire it per RM-1.5), unify ruff/mypy configs + delete pyrightconfig or align it, unify fresh-emitter stamp/grid, harvest display dedup registries into MH (seeded — the P5-F4 fix), collapse scipy/penalty triplication | RM-1.* | 3/3/2/2 |
| RM-5.2 | Dead-code tail removal with recorded sequencing: FSCache tests migrate BEFORE sync-adapter deletion; F20 rows are unreachable-not-unimported (unwire, then delete); state machine, TokenBudgetManager, diarization, genre classifier, stale context builders + phantom-schema conftest fixture, Section model, compat converters, style_transfer, active_learning 3/4, simplify_rdp, SequenceAnalyzer chain | RM-1.5, RM-3.3 | 2/2/2/2 |
| RM-5.3 ⚖ | Extract the corpus 4-pack (FE/feature_store/recipe_builder/profiling, ~24k LOC incl. tests) to a sibling repository; cut the 3 display-side import sites; fix uuid→content-hash identity on the way out | RM-G2 | 3/3/2/2 |
| RM-5.4 | Display pipeline: document DEFER status + the P5 defect register in-tree so revival starts from truth, not archaeology | — | 2/1/1/1 |
| RM-5.5 | Documentation truth pass: user guide knob table regenerated from wired config only; six-channel claim; multi-agent architecture docs; phantom paths; replace the "dozens of hours" claim with measured numbers from RM-1.6/2.1 | RM-1.5, RM-2.1 | 4/2/1/1 |

## Stage 6 — Reactivation verification (P1 gate at the end)

| Item | What |
|---|---|
| RM-6.1 | Full `make validate` green in CI from a clean checkout (mutating steps guarded); golden render suite green; xLights 2026.15 acceptance test green |
| RM-6.2 | One committed end-to-end evidence artifact: audio → `.xsq`/`.xtiming` → imported into xLights → eval-report scores + a human's recorded judgment — the first in the project's history |

## Readiness classification

**REQUIRES_STABILIZATION.**

Rationale: the product premise survives review (the thesis space is verified
unoccupied; the deterministic core and renderer are genuinely valuable); subsystem
internals are consistently better-engineered than their integration seams; every
defect found has a bounded, evidenced fix; and no data-loss/security catastrophe
exists on the shipped path. But the shipped output does not currently represent the
design intent (CF-1/2/6/7), the system cannot measure its own quality (SF-4, CC-4),
and the engineering gates do not hold from a clean checkout (SF-7). It is NOT
REQUIRES_MAJOR_REWORK: nothing foundational needs rearchitecting to reach the
decision point — the architectural fork (RM-2.3) is deliberately deferred until the
system can measure it honestly.

**Exit criteria (to READY_WITH_TARGETED_REMEDIATION):** Stage 0 complete + RM-1.0/1.1/
1.2/1.4/1.6 landed + RM-G1 decided. **Exit to READY:** Stage 6 both items green +
RM-2.2/2.3 decided and implemented.

**Blockers that are decisions, not code:** LICENSE (RM-G1), product boundary
(RM-2.2), LLM boundary (RM-2.3), corpus extraction (RM-5.3), Python 3.13 (RM-3.3).
