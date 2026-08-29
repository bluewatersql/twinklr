---
type: change
status: active
area: quality
created: 2026-08-29
updated: 2026-08-29
---

# Post-refactor validation — implementation plan

_Plan for [spec.md](spec.md). Executes a five-phase validation campaign that proves the
refactored engine still works end to end, then locks a regression baseline. Phase 0 is a
deliberate code-review pass whose findings refine Phases 1–4 before they run._

> **Owner authorization on file (2026-08-29):** live provider/model calls are authorized
> for this change. Bounded, logged, cost-capped usage per Phase 3. Sealed ledgers from
> `twinklr-reactivation-review` (P3-T4 two-attempt cap, P3-T7 terminal image proof) are
> **not** reopened by this authorization.

## Guiding principles

- **Evidence over assertion.** Every "works" claim carries fresh command output. Merged
  code and mocked tests are not acceptance (inherited rule).
- **Offline first, live last.** Build deterministic safety nets before spending live
  calls, so a live failure is diagnosable against a known-good offline baseline.
- **Final-output parity is the bar, not intermediate matching.** (Owner note 2026-08-29.)
  Intermediate artifacts (`audio_profile.json`, `macro_sections.json`,
  `choreography_plan.json`) do **not** need to match — they are diagnostic only. The
  validation bar is that the **final delivered output** is on par with what was previously
  delivered: the emitted `.xsq` for MH sequencing should be similar or identical (allowing
  for natural LLM variation) and exhibit the **same level of advanced/technical
  implementation detail** (channel coverage, effect richness, coordination sophistication,
  timing precision). The harness is a checkpoint to confirm "still works as expected," not
  a bit-exact museum.
- **Executor/verifier separation** and worktree isolation per the campaign's
  [orchestration model](../twinklr-reactivation-review/build/plan/00-overview.md).
- **No fabricated owner judgment.** Human-taste gates are run mechanically and recorded;
  their verdicts stay with the owner.

## Definition of done (this change)

1. Phase 0 functional-inventory doc committed under this change.
2. Offline regression harness green and wired into `make validate`.
3. CI-runnable replay E2E + provider-contract smokes green.
4. ≥1 live full-pipeline show produced, valid, cost-logged, parity-assessed.
5. Locked tracked baseline + owner-reviewed human-QA-readiness checklist.
6. `make validate` passes with fresh output; `context/current-state.md` updated;
   `ACTIVE.md` reflects status; durable lessons promoted to `memories/`.

---

## Phase 0 — Current-state code review & functional inventory

**Goal:** replace prose status with a file-level, verifiable inventory of what actually
works, what is stubbed/mocked, and what is partially complete — so Phases 1–4 target the
real gaps. This phase is **read/analysis only**; it produces a document, not code.

**Why it's needed:** the refactoring touched emission, coordination, provider transport,
config, and the ML chain. The handoff tracks status narratively across many commits; a
single consolidated, evidence-backed inventory does not yet exist.

**Work items**

- P0-1 Map the runnable surface: enumerate CLI entry points (`twinklr run`, `display`,
  `show`, iteration/`inject`/`regenerate`, catalog, recipe-builder, `show-eval`) to their
  pipeline definitions and stages (`packages/twinklr/core/pipeline/`, `cli/`).
- P0-2 Trace each pipeline stage to its real vs. stubbed dependencies (which stages call a
  live provider, which are deterministic). Flag every place tests inject `AsyncMock`.
- P0-3 Inventory the provider/transport layer post-`P4-T4` consolidation: retry ownership,
  HTTP/cache lifecycle, the model-capability policy that now gates `temperature`/reasoning
  (the P3-T4 failure root cause). Confirm the capability policy covers the models we will
  call live in Phase 3.
- P0-4 Inventory partial/incomplete features and their exact disposition (see the carried
  inventory table below); confirm each against code, not just the handoff.
- P0-5 Audit test topology: unit vs. offline-integration vs. skipped-live; identify what a
  green `make validate` does and does **not** prove. Fix the stale `Makefile`
  `test-integration`/`test-unit` targets (they point at non-existent files).
- P0-6 Confirm the shape/fields of the `artifacts/` baselines to pick comparison keys for
  Phase 1.

**Deliverable:** `changes/post-refactor-validation/notes/functional-inventory.md`
(working/stubbed/partial matrix with `file:symbol` evidence and per-item disposition).

**Exit:** inventory reviewed; Phases 1–4 task lists adjusted to match findings; open
questions below resolved or explicitly deferred.

**Suggested allocation:** one `explore`/`code-explorer` pass per subsystem (pipeline,
provider, emission/export, audio, feature-engineering), synthesized by the orchestrator.

---

## Phase 1 — Offline regression safety net (structural parity vs. `artifacts/`)

**Goal:** detect semantic drift introduced by the refactoring without any live call, by
comparing current deterministic output against curated pre-refactoring baselines.

**Work items**

- P1-1 Select 2–3 representative baselines from `artifacts/` (candidates: `11_need_a_favor`
  MH show, `titanium…` MH show, `02_rudolph…` display show — they cover MH, display, and
  trace outputs). Promote the chosen inputs+outputs into a **tracked** fixture location
  under this change (they are currently gitignored and could vanish).
- P1-2 Define the comparison contract **on the final `.xsq` output** (the delivered
  product), not intermediate JSON. Parity-critical: element/effect structure, MH
  channel coverage and DMX richness, effect-type diversity, coordination/layering
  sophistication, and timing/beat-grid alignment — i.e. the "level of advanced/technical
  implementation detail" must be on par. Tolerated: natural LLM variation in specific
  choices, timestamps, run/session ids, cost, provider metadata, and legitimately
  nondeterministic ordering. Intermediate artifacts are captured only as diagnostics to
  explain a final-output divergence, never as pass/fail gates.
- P1-2a Derive quantitative `.xsq` "sophistication" metrics so parity is measurable rather
  than eyeballed (e.g. distinct effect types, channels exercised, effect/section density,
  transition count, coordination-mode variety). Compare current vs. baseline on these.
- P1-3 Build a structural-diff harness (new `tests/regression/` module) that re-runs the
  offline/replayed pipeline for each baseline and asserts the parity contract. Reuse the
  existing golden infrastructure patterns (`tests/golden/harness.py`, `--regen-goldens`).
- P1-4 Where current output legitimately differs from prior state (intended refactoring
  behavior change), record the diff + rationale rather than forcing equality; get owner
  sign-off on each intentional divergence.
- P1-5 Wire the regression suite into `make validate` (default offline path).

**Exit:** regression harness green (or every red explained + owner-accepted as intended
change), runnable in CI, committed with fresh output.

---

## Phase 2 — Automated E2E in CI (cache-replay) + provider-contract smokes

**Goal:** make "audio → plan → render → `.xsq`" runnable and asserted in CI without paid
calls, and catch the provider-contract failure classes offline.

**Work items**

- P2-1 Record provider responses for one full run per baseline song into a replay fixture
  (leveraging the prompt/schema-aware cache and the P3-T7 zero-call replay pattern).
- P2-2 Add a full-pipeline replay E2E (new `tests/e2e/`, or extend `tests/integration/`)
  that drives the real CLI/pipeline with the replay fixture and asserts valid artifacts +
  Phase 1 parity keys — no `AsyncMock` on the planning path.
- P2-3 Add offline provider-contract smokes asserting request shape against provider
  rules: no `$ref` beside sibling keys (attempt-1 failure), `temperature` omitted for
  models that reject it via the capability policy (attempt-2 failure), strict
  structured-output schema validity. These must fail on a pre-fix/adversarial case.
- P2-4 Document how to refresh replay fixtures when prompts/schemas change.

**Exit:** replay E2E + contract smokes green in CI; the two P3-T4 failure classes are
provably caught offline.

---

## Phase 3 — Live end-to-end validation (authorized)

**Goal:** demonstrate the real, live pipeline produces a valid show at prior-state
functional level. This is the handoff's pivotal "one meaningful non-GUI end-to-end show."

**Work items**

- P3-1 Pre-flight the live macro-planning path offline against Phase 2 contract smokes so
  we do not repeat P3-T4's paid failures. Confirm the capability policy for the exact
  model(s) to be used.
- P3-2 Run the full pipeline live on 1–2 baseline songs end to end (audio → live plan →
  render → `.xsq` + timing). Bounded, cost-capped, logged per run; record token usage and
  USD. (Owner to confirm model + per-run/total cap — see open questions.)
- P3-3 Assess parity: run the live output through the Phase 1 structural contract against
  its pre-refactoring baseline; record intended vs. unintended differences.
- P3-4 (Optional, owner-gated) Exercise the live vision-judge/eval path (P2P-T6 mechanics)
  and the Ollama schema smoke (P4-T2). Owner note 2026-08-29: an **Ollama cloud-hosted
  model** may be used to expedite testing instead of pulling a multi-GB local model — this
  proves the provider/schema path without the local-model download blocker (note the P4-T2
  contract's "local-only" framing is then validated against a cloud endpoint; record that
  distinction). Run the mechanics; do not fabricate taste verdicts.
- P3-5 (Deferred, but unblocked by this phase) note xLights GUI acceptance can now be
  scheduled per `tests/golden/test_xlights_acceptance.py` once the owner runs a local
  xLights session.

**Exit:** ≥1 live show produced and valid; parity assessed and recorded; costs logged.

---

## Phase 4 — Lock baseline + human-QA readiness

**Goal:** freeze the validated state as the go-forward baseline and define exactly what
human QA should (and should not) do.

**Work items**

- P4-1 Promote the validated outputs (offline replay + the live run) to the locked tracked
  baseline the regression harness pins against.
- P4-2 Write the human-QA-readiness checklist: what is automated-covered, what still needs
  human eyes (creative taste, xLights GUI import, calibration ranking), and the exact
  runbook/expendable-show constraints.
- P4-3 Update `context/current-state.md` with the empirical E2E evidence; update the
  reactivation-review phase-exit notes that this evidence satisfies; promote lessons to
  `memories/`.
- P4-4 Close this change in `ACTIVE.md`, leaving artifacts as history.

**Exit:** baseline locked; checklist accepted; docs/indexes updated; change closed.

---

## Carried inventory — partially complete / incomplete features

Confirmed in Phase 0; disposition set here so nothing is silently dropped.

| Item | State (from handoff) | Disposition in this change |
|---|---|---|
| P3-T4 live macro-plan acceptance | 2 attempts failed, cap exhausted | Superseded — Phase 3 does a fresh live E2E under new authorization (does not reopen the sealed ledger) |
| P4-T2 real Ollama smoke | No local model pulled | Phase 3.4 — use Ollama **cloud-hosted** model to expedite (owner-approved 2026-08-29); no local download needed |
| P4-T7 MH idiom-mining spike | NO-GO / deferred, corpus-gated | Out of scope; remains deferred |
| P2P-T6 vision calibration | Live/blinded ranking pending | Run mechanics in Phase 3.4; owner owns verdict |
| P2P-T13 / D1 three-arm | Harness only, no result | Out of scope for parity; note as separate owner experiment |
| Phase 2K real-corpus exit | Tooling only | Out of scope; needs owner corpus |
| Phase 1P xLights GUI + human judgment | Deferred | Unblocked (not performed) by Phase 3; scheduled after |
| WhisperX / TorchCodec runtime | Deferred under FFmpeg 9 | Out of scope; keep deferred |
| Stale `Makefile` test targets | Point at missing files | Fixed in Phase 0.5 |
| `artifacts/` not a tracked baseline | Gitignored, no regression use | Resolved in Phases 1 & 4 |

## Testing strategy summary

- **Unit** (existing, ~5,637 tests) — keep green throughout via `make validate`.
- **Offline structural regression** (new, Phase 1) — parity vs. curated baselines.
- **Replay E2E** (new, Phase 2) — real pipeline, recorded provider responses, in CI.
- **Provider-contract smokes** (new, Phase 2) — catch P3-T4 failure classes offline.
- **Live E2E** (Phase 3) — bounded, authorized, cost-logged; the acceptance evidence.
- **Local-only/GUI** (existing, skipped in CI) — scheduled after the live milestone.

## Open questions / prerequisites before execution

1. **Live model + budget (Phase 3):** which model for macro planning (the failed attempts
   used `gpt-5.6-sol`, which rejects `temperature`)? What per-run and total USD cap?
2. **Baseline songs:** OK to use `11_need_a_favor`, `titanium…`, `02_rudolph…` as the
   canonical parity set, and are their source audio files still available locally?
3. **Intended-divergence authority:** who signs off when current output legitimately
   differs from prior state (i.e., the refactoring changed behavior on purpose)?
4. **Tracked-baseline location/size:** acceptable to commit a curated subset of
   `artifacts/` (a few hundred KB of `.xsq`/JSON) into a tracked fixture path, given
   `artifacts/` is otherwise gitignored?
5. **Ollama (Phase 3.4):** ~~pull a named local model, or waive?~~ **Resolved
   2026-08-29** — use an Ollama cloud-hosted model to expedite the schema smoke; which
   cloud model (e.g. `kimi-k3:cloud`, `deepseek-v4-pro:cloud`, `glm-5.2:cloud`, per the
   installed `ollama list`)?
6. **Branch/worktree:** new branch off `main` at `54948c0` with worktree-isolated
   executor/verifier lanes, matching the campaign model — confirm.

## Risks

- **Silent semantic drift** the parity contract doesn't cover — mitigate with a
  conservative, reviewed field selection and owner sign-off on divergences.
- **Live cost/failure repeat** of P3-T4 — mitigate by gating every live run behind the
  Phase 2 contract smokes and a hard cap.
- **Baseline is itself stale/wrong** (pre-refactoring output had bugs) — treat parity as
  "no unexplained regression," not "identical"; record known prior-state defects.
- **Non-determinism** in offline replay — pin seeds, caches, and clock where the pipeline
  allows; exclude volatile fields from comparison.
