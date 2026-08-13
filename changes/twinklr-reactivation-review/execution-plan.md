# Twinklr Reactivation Review — Execution Plan

_Status: **APPROVED 2026-08-13** — approved as written, with amendment: execute using
OMC autopilot + ultrawork + team orchestration modes. `EXECUTION_MODE=discovery-only`,
`RUNTIME_MODE=local-safe` confirmed. Autopilot Phases 0–1 (spec/plan) are satisfied by
this document; autopilot's execution phase maps to review Stages 0–1, its validation
phase maps to the discovery-gate critic challenge; the run stops at the discovery gate.
Team workers are named read-only agents (sonnet tier); no Haiku anywhere per user
directive. Created 2026-08-13._

## 1. Run configuration (proposed)

```text
CHANGE_SLUG    = twinklr-reactivation-review
EXECUTION_MODE = discovery-only        # default; user may elect continuous at approval
RUNTIME_MODE   = local-safe            # read-only checks preferred; no paid LLM calls
BASELINE_REF   = aa8d325bca6e83d9be0853e5842759bc7bcb8d1e (main, clean worktree)
Host           = Darwin 25.5.0, Python 3.14.6, uv 0.12.3
```

- `changes/ACTIVE.md` currently lists no active changes — this slug is free; no merge
  conflict with prior work.
- Pre-existing working tree is clean; `git status --short` was empty at baseline.
- `external-enabled` actions (paid LLM calls, credentialed APIs, model downloads,
  network writes) are **out of scope** unless separately authorized.

## 2. Model and platform constraints

User directive: **no Haiku**. Permitted models: sonnet, opus, fable, gpt sol, codex.

Availability in this environment (Claude Code harness):

| Model | Available | Use |
|---|---|---|
| Fable (fable) | yes (orchestrator + `model=fable` override) | orchestration, synthesis, final assessment |
| Opus (opus) | yes | architecture/product evaluation, adversarial verification |
| Sonnet (sonnet) | yes | discovery fan-out, phase source review, mechanical tracing |
| Haiku | **excluded by directive** | never; `oh-my-claudecode:writer` (Haiku-pinned) will not be used |
| GPT Sol / Codex | **not reachable from this harness** | cannot be dispatched; noted as a limitation |

All subagent dispatches will carry an explicit `model=` override (sonnet/opus/fable) so
no agent silently falls back to a default that includes Haiku.

## 3. Orchestration design

Orchestrator: this session (Fable). It owns stage gating, dispute resolution, manifest
state, and all canonical documents. Subagents receive bounded scopes with explicit inputs
and outputs; authoring and adversarial verification are always different agents.

### Stage → agent → model map

| Stage | Work | Agent type(s) | Model |
|---|---|---|---|
| 0 Bootstrap & governance | instruction load, baseline record, spec/plan/ACTIVE.md, capability inventory | orchestrator directly | fable |
| 1 Repository reconstruction | parallel read-only fan-out over subsystems (packaging, CLI/entry points, audio analysis, LLM planning, rendering/xLights, corpus/feature store, tests/CI); execution-path tracing | `Explore` + `feature-dev:code-explorer` (read-only), 5–7 parallel | sonnet |
| 1 Discovery synthesis | merge maps into `reviews/discovery.md` + `reviews/manifest.md` | orchestrator | fable |
| Discovery gate | independent challenge of coverage, phase boundaries, system model | `oh-my-claudecode:critic` | opus |
| 2 Product thesis & approach | product boundary, success criteria, alternative architectures | `oh-my-claudecode:architect` (authoring) + orchestrator synthesis | opus / fable |
| 3 Phase source reviews (×~6) | deep review per phase doc (scope, contracts, correctness, alternatives, findings) | `general-purpose` reviewers, one per phase, parallel where independent; security dimensions via `oh-my-claudecode:security-reviewer` | opus (architecture-heavy phases: foundation, LLM planning, rendering); sonnet (audio analysis, corpus, interfaces/engineering) |
| 4 Runtime & baseline validation | `make env-check`, ruff check-only, mypy, pytest, CLI help, fixture-backed offline paths; `make validate` only under safe-worktree conditions | orchestrator via Bash (+ `EnterWorktree` if mutation-safe run needed) | fable |
| 5 Cross-cutting synthesis | system-level pass, structural classifications, dispositions | `oh-my-claudecode:architect` + orchestrator | opus / fable |
| 6 Modernization assessment | dependency/tooling currency vs `uv.lock`, official-doc checks with URLs + access dates | `oh-my-claudecode:document-specialist` (WebSearch/WebFetch) | opus |
| 7 Adversarial verification | non-author challenge of every major finding; verdicts ACCEPTED/REVISED/REJECTED/DISPUTED | `oh-my-claudecode:critic` + `feature-dev:code-reviewer` (never the authoring agent) | opus |
| 8 Remediation design & readiness | normalized findings, prioritized dependency-aware roadmap, readiness classification | orchestrator; plan critique by `oh-my-claudecode:critic` | fable / opus |

Rules enforced across all stages:

- A phase's author never solely verifies its own findings (Stage 7 assigns disjoint
  reviewers; the orchestrator records both verdict and evidence).
- Parallel agents get non-overlapping scopes fixed at the discovery gate; shared
  architectural conclusions are resolved only by the orchestrator.
- Every accepted finding cites repo-relative paths/symbols and the baseline SHA, with
  OBSERVED/INFERRED/PROPOSED/UNKNOWN labels.

### Skills and tools

- `superpowers:dispatching-parallel-agents` — governs the Stage 1 and Stage 3 fan-outs.
- `superpowers:verification-before-completion` — before any completion or gate claim.
- Repo workflows: `prompts/INDEX.md` procedures, `prompts/handoff/session-closeout.md`
  at closeout; templates from `templates/change.md` and `templates/handoff.md`.
- Read-only inspection: Read/Grep/Glob, LSP tools (`lsp_document_symbols`,
  `lsp_find_references`) for caller/consumer tracing.
- Runtime: `make env-check`, `uv run ruff format --check .`, `uv run ruff check .`,
  `uv run mypy .`, `uv run pytest tests/ -v` — check-only forms first; classification
  of failures as BASELINE/NEW/ENVIRONMENTAL/NOT_RUN against
  `memories/learnings/known-test-failures.md` (re-verified, not trusted).
- External docs (Stage 6 only): WebSearch/WebFetch of official primary sources, recorded
  with URL and access date. No credentialed or paid calls.
- OMC/`.omc/`, `.remember/`, and agent auto-memory are treated as machine-local caches,
  never authority; scanner dumps and temp output go to the session scratchpad.

Explicitly **not** used: `oh-my-claudecode:writer` (Haiku), autopilot/ralph/ultrawork
autonomous modes (this review needs gated, auditable stages), any code-modifying agents
against application source (review-only boundary).

## 4. Artifact plan

```text
changes/twinklr-reactivation-review/
├── execution-plan.md      (this file)
├── spec.md                (from templates/change.md, Stage 0)
├── plan.md                (phase-aware, Stage 0, updated at every gate)
├── handoff.md             (from templates/handoff.md, before any pause)
└── reviews/
    ├── discovery.md       (Stage 1)
    ├── manifest.md        (Stage 1, living document)
    ├── product-and-approach.md        (Stage 2)
    ├── phases/<phase-slug>.md         (Stage 3, ~6 docs)
    ├── findings.md        (Stage 5+, normalized schema)
    ├── cross-cutting.md   (Stage 5)
    ├── verification.md    (Stages 4+7)
    ├── remediation-roadmap.md         (Stage 8)
    └── final-assessment.md            (Stage 8)
```

Created lazily — only when its stage begins. `changes/ACTIVE.md` gains this review at
Stage 0 and is corrected at closeout. Durable truths promote to `context/`; durable
lessons to `memories/` with provenance; nothing generated/local gets committed.

## 5. Review-only boundary (restated commitments)

- No changes to application code, tests, dependencies, lockfiles, or generated artifacts.
- No deploys, pushes, PRs, or external writes. No secrets in commands or documents.
- `make validate` (which mutates via format/lint-fix) runs only in a safe clean worktree
  with before/after `git status` recorded, or its omission is documented.
- Pre-existing user changes: none at baseline (clean tree); if any appear they are
  user-owned and untouched.

## 6. Proposed phase decomposition (Stage 3 candidates, to be validated at discovery gate)

1. `foundation-and-orchestration` — config, caching, I/O, logging, API clients, pipeline
   execution, workspace packaging. (opus)
2. `deterministic-audio-analysis` — metadata, rhythm, energy, structure, harmonic,
   lyrics/phonemes, timelines, validation. (sonnet)
3. `llm-agents-and-planning` — runtime prompt packs, Pydantic schemas, provider adapters,
   planner/validator/judge iteration. (opus)
4. `rendering-and-xlights` — sequencing models, moving heads, display, templates, curves,
   `.xsq` I/O fidelity. (opus)
5. `corpus-intelligence` — feature engineering, SQLite feature store, recipes, embeddings,
   evaluation/reporting. (sonnet)
6. `interfaces-and-engineering` — CLI, scripts, fixtures, test architecture, CI, docs
   toolchain. (sonnet)

Boundaries may be re-cut after Stage 1 evidence; changes recorded in `plan.md`.

## 7. Stop conditions and gates

- **Discovery gate** (end of Stage 1): all first-party areas dispositioned in manifest,
  phase scopes non-overlapping, critic challenge passed, unknowns explicit. If
  `EXECUTION_MODE=discovery-only`: stop here, write `handoff.md`, report plan +
  highest-risk unknowns.
- **Per-phase**: phase doc complete with candidate findings before Stage 7 verification.
- **Pre-closeout**: definition-of-done checklist from the review prompt §7 verified item
  by item with fresh evidence.
- **Hard stops**: any action requiring external authorization; any instruction conflict
  between repo sources (resolved from evidence, never silently); budget/context
  exhaustion (handoff written first).

## 8. Known limitations (recorded up front)

- GPT Sol and Codex models cannot be dispatched from this harness; all agent work uses
  sonnet/opus/fable.
- `RUNTIME_MODE=local-safe` means no live OpenAI-backed pipeline runs; LLM-path behavior
  is assessed from code, fixtures, and offline tests only.
- Python 3.14.6 on host vs. project's declared Python 3.12 — environment mismatch risk
  will be checked at Stage 4 (`make env-check`, uv-managed interpreter) and classified
  ENVIRONMENTAL if it blocks validation.
