# Memories — Shared Project Memory

`memories/` is the repository's shared long-term memory: what was learned building
Twinklr. It is Git-tracked, reviewed, and shared by every tool. It is not agent-native
auto-memory ([memory policy](../context/agents/memory-policy.md)). Current truth belongs
in `context/`; memories explain why, and what we learned.

| Directory | Holds |
|---|---|
| [`decisions/`](decisions/) | Accepted architecture and process decisions with rationale |
| [`learnings/`](learnings/) | Evidence-backed, non-obvious lessons |
| [`constraints/`](constraints/) | Durable limitations that shape design |
| [`patterns/`](patterns/) | Validated reusable techniques |
| [`inbox/`](inbox/README.md) | Unverified candidates awaiting promotion (empty is healthy) |

## Decisions

- [llm-plans-intent-renderer-implements-precision.md](decisions/llm-plans-intent-renderer-implements-precision.md) — accepted boundary; includes the dated narrow-channel baseline and the 2026-08-14 schema-v2 implementation resolution, superseded for moving heads on 2026-11-16 (D1 comparison still pending)
- [keep-dsp-after-mir-ab.md](decisions/keep-dsp-after-mir-ab.md) — accepted P2P-T8 decision: retain the current DSP rhythm/structure default because model arms did not produce complete local evidence
- [lane-blend-mode-overrides-recipe.md](decisions/lane-blend-mode-overrides-recipe.md) — accepted P3-T2 precedence: lane blend intent uniformly overrides recipe blend metadata in the emitted sub-layer space
- [typed-macro-coordination-contract.md](decisions/typed-macro-coordination-contract.md) — accepted P3-T4 decision: exact four-field typed macro contract, palette/focal precedence, amended AC2 typed-reader boundary, and P3-T5 behavioral-consumption ownership
- [coordinated-show-contract.md](decisions/coordinated-show-contract.md) — accepted P3-T5 decisions: one combined command/graph/BeatGrid, concrete-target focal budgets, strict ownership and call/response policy, shared palette projection, safe registry preservation, and the retained P3-T3 catalog edge; the moving-head focal and palette projection was superseded on 2026-11-16
- [unified-xlights-emission-contract.md](decisions/unified-xlights-emission-contract.md) — confirmed P3-T6 decision: display and moving heads share one renderer-neutral xLights emission core; exact rules remain in its specification
- [p3-t4-live-acceptance-superseded.md](decisions/p3-t4-live-acceptance-superseded.md) — owner decision 2026-11-12: P3-T4 live macro acceptance is closed by the 2026-08 OpenAI and 2026-11-12 Claude live runs; the sealed ledger stays untouched
- [display-stays-lit.md](decisions/display-stays-lit.md) — owner direction 2026-11-12: every section keeps the display lit; brightness floor, beat grid extended to song end, and a foundation-coverage rule in the group planner
- [mh-single-renderer.md](decisions/mh-single-renderer.md) — owner direction and look acceptance 2026-11-16: one moving-head renderer (profile-based, complete DMX frames); the old renderer, its templates and switches deleted; the accepted look, guarded by the output pins, is the reference; the cutover regressed the planner's song intent, which the owner directed be rendered (2026-11-17)
- [mh-song-outranks-the-arrangement.md](decisions/mh-song-outranks-the-arrangement.md) — integrator decision 2026-11-18 (owner may reverse): no arrangement choice (variation, density, modifiers) may make a song event worse than the reference; tries all units together first, then falls back to plan order when the render would harm a song event or a modifier would drop more of a cue
- [mh-render-matches-pre-cleanup-look.md](decisions/mh-render-matches-pre-cleanup-look.md) — **superseded 2026-11-16** by `mh-single-renderer.md`; was: the pre-clean-up look of the deleted renderer is the reference (history)

## Learnings

- [reactivation-review-2026-08.md](learnings/reactivation-review-2026-08.md) — historical `aa8d325` review conclusions (readiness, verified defect classes, external facts, strengths), with a pointer to current campaign truth
- [known-test-failures.md](learnings/known-test-failures.md) — historical gate baseline at `aa8d325` (2026-08-13): 120 failures classified; superseded by the green integrated campaign gate
- [live-provider-run-lessons.md](learnings/live-provider-run-lessons.md) — live provider lessons: reasoning models reject temperature, 300 s timeout, config schema drift, degenerate-segment aborts, Claude rejects planner schemas as too large to compile, Ollama Cloud ignores `response_format`, proxy TLS
- [simplification-pass-2026-02.md](learnings/simplification-pass-2026-02.md) — stale auto-memory case study: a claimed simplification pass that never landed on `main`
- [prove-parity-before-deleting.md](learnings/prove-parity-before-deleting.md) — before deleting a replaced implementation, compare old and new on the same inputs; unchanged bytes on the surviving path did not show that the moving-head cutover lost the planner's song intent (2026-11-17)
- [mh-defects-hide-on-idealized-rigs.md](learnings/mh-defects-hide-on-idealized-rigs.md) — test moving-head mechanisms on rigs with narrowed allowed ranges and slow heads, render the owner's song after each feature, and judge rule changes by comparing events before and after (2026-11-18)
- [model-dump-hashes-rekey-caches.md](learnings/model-dump-hashes-rekey-caches.md) — removing or renaming a hashed model field changes session ids, planner cache keys, live-plan digests and fingerprints: paid re-plans and `regenerate` refusals to tell the owner about

## Constraints

- [python-3.12-only.md](constraints/python-3.12-only.md) — Python 3.13 is the only supported minor (3.14 excluded); the file keeps its former-constraint name because historical change documents link to it

## Patterns

- [code-patterns.md](patterns/code-patterns.md) — codebase idioms verified against `main` with source citations, including refusing removed config keys by name
- [render-output-proof.md](patterns/render-output-proof.md) — proving a refactor leaves render output unchanged: a byte matrix against a baseline commit, then committed pins; not a proof of parity with a deleted implementation

## Rules

Not a memory: TODOs, transient errors or debugging state, unverified ideas (use `inbox/`),
transcripts or model reasoning, current truth (`context/`), active work (`changes/`),
agent-local or machine-specific state, secrets.

To add or update: search this tree and `context/` for an existing owner and update rather
than duplicate; require evidence (code, tests, recorded runs, incidents, repeated
experience); record provenance and date in frontmatter
([schema](../context/INDEX.md#metadata-convention), starters in
[`../templates/`](../templates/)); link related pages; update this index. Delete memories
proven wrong. Workflow:
[`../prompts/handoff/session-closeout.md`](../prompts/handoff/session-closeout.md).
