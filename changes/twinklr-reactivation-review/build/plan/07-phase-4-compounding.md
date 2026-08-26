# Phase 4 — Compounding (M4)

_Goal: modern platform, retired debt, honest docs, optional capabilities. Nothing
here blocks the product; everything here reduces friction for whatever comes next.
Proposal M4; D7/D12 + recorded debt-sequencing constraints._

**Exit criteria:** modern ML chain on Python 3.13; dead tail removed without
breaking anything (sequencing constraints honored); user guide describes only wired
behavior; local-provider option available.

**Execution status (2026-08-26):** P4-T1 through P4-T6 are independently verified and
integrated (**6/7**). P4-T2's implementation and redirect-hardening remediation are
integrated through `3765bd9`/`40e8e55`, but its real Ollama schema smoke remains
unclaimed pending explicit local opt-in. P4-T3 is integrated at `bf6bba5`, P4-T4 at
`3e7f679`, P4-T5 at `05f24d0`, and P4-T6 at `da8f19d`. P4-T7 full execution is
NO-GO/deferred on its unsatisfied P2K-T2 empirical dependency and the absence of an
accessible, provenance-bearing moving-head corpus manifest. Its independently approved
repository-only preflight is integrated at `c79566e`; that preflight is not task
completion and makes no feasibility verdict. Phase exit is not declared. Exact
task evidence remains single-owned by the
[P4-T2](../specs/phase-4-compounding/P4-T2-local-provider-option.md),
[P4-T3](../specs/phase-4-compounding/P4-T3-dead-tail-retirement-wave-1.md),
[P4-T4](../specs/phase-4-compounding/P4-T4-duplication-collapse.md),
[P4-T5](../specs/phase-4-compounding/P4-T5-dead-config-final-sweep.md),
[P4-T6](../specs/phase-4-compounding/P4-T6-documentation-truth-pass.md), and
[P4-T7](../specs/phase-4-compounding/P4-T7-mh-idiom-mining-exploration.md) task specs.

## Tasks

| ID | Title | What (summary) | Evidence | Deps | Executor | Verifier |
|---|---|---|---|---|---|---|
| P4-T1 | ML chain + Python bump (D7) | One coordinated change: delete the orphaned diarization module FIRST (pyannote-4.x breakage concentrates there), then torch/torchaudio 2.8.x + whisperx 3.8.6 + pyannote 4.x + Python 3.12→3.13 ⚖; update the constraint memory; watch item: torchaudio maintenance wind-down (TorchCodec migration) — prefer deps that dropped it. | D7, M3 modernization | Phase 2P merged | opus | opus |
| P4-T2 | Local provider option (D12) | Provider config for Ollama via OpenAI SDK `base_url`; structured outputs route via `/v1/chat/completions` `response_format` (the `/v1/responses` gap is documented); target models benchmarked against OUR schemas (`qwen3.5:27b` / `granite4.1:30b` / `nemotron-3.5-lightning` class); offline-December smoke test. | D12 research | P2P-T11 | sonnet | opus |
| P4-T3 | Dead-tail retirement wave 1 (safe) | Remove with recorded sequencing honored: migrate FSCache tests to `tests/unit/caching/` FIRST then delete the sync-adapter; unwire-then-delete the two "unreachable at runtime but imported" curve rows (modifiers, providers/native — deleting without unwiring breaks the build); diarization goes in P4-T1; orphaned audio modules (genre classifier, stale context builders + the phantom-schema conftest fixture, dead Section model, dead tempo-changes twin incl. its public re-export), display compat converters, `SequenceAnalyzer` chain, `simplify_rdp`. | P1-F29/F31, P4-F20 (corrected), P2/P5/P6 dead inventories | Phases 1P/3 merged | sonnet | opus |
| P4-T4 | Duplication collapse | One OpenAI client + one retry policy (SDK `max_retries` explicit — kills the ≤9-requests amplification); one `configure_logging` (wire or delete `AppConfig.logging`); conversation-store eviction; httpx client lifecycle (aclose); scipy/penalty triplication collapse. | CC-6, P3-M-F/M-H, P2-M10/F21/F23 | P2P merged | sonnet | opus |
| P4-T5 | Dead-config final sweep | Every remaining CC-1 member is wired-with-a-behavior-test or deleted-with-docs — no third state; acceptance = a generated knob-inventory test asserting every documented config key has an observable effect. | CC-1, RM-1.5 | P1P/P2P/P3 wiring done | sonnet | opus |
| P4-T6 | Documentation truth pass | User guide regenerated from wired config only; six-channel claim now true (post schema-v2) or corrected; architecture docs match the shipped loop; phantom paths removed; "dozens of hours" replaced by measured numbers from the eval harness; scripts/ triage (promote/delete per P7 table). | SF-8, P7-M2/M3, measured data | P4-T5 | sonnet | opus |
| P4-T7 | MH-idiom mining exploration (optional) | Feasibility spike over an independently reverified, accessible DMX moving-head corpus; if propensity/idiom extraction works for MH, part 1 joins the knowledge loop. Time-boxed; outcome = a decision memo, not a feature. Current full-execution status: NO-GO/deferred on P2K-T2 empirical exits and an accessible MH corpus manifest. | M4, D5 convergence note | P2K-T2 | opus | opus |

## Notes for spec authors

- T3's spec must enumerate every deletion with its verified zero-callers evidence AND
  its sequencing constraint — this is where "actionable-and-wrong" F20-style rows
  would do damage; copy the corrected labels.
- T5's knob-inventory test is the phase's real deliverable: it makes dead config a
  CI-detectable class forever.
- T7 is deliberately last and optional — it must not leak scope into earlier phases.

## P4-T7 safe preflight record — 2026-08-26

Full execution did not start. P2K-T2 has verified tooling but still lacks the author's
real-corpus mining run, idempotent rerun evidence, non-empty support/stability
distributions, and owner-authored threshold decision log. A filename-only local
preflight found no accessible MH corpus manifest and no `.xsq`, `.xsqz`, or vendor
archive under the inspected `data/` paths. No corpus content was opened or parsed.

Decision: **NO-GO / defer** until both triggers are satisfied: (1) P2K-T2's empirical
owner-corpus exits are accepted, and (2) an accessible manifest identifies sufficient
moving-head sequences for the time-boxed spike. This does not complete P4-T7 and does
not answer its feasibility questions.

The follow-on repository-only preflight was independently approved and integrated at
`c79566e`. It corrects the plan row's unsupported deleted-vendor-history premise,
records reusable seams and structural walls, and pins the exact five re-entry artifacts
plus the isolated 165-minute/180-minute-capped offline plan. Approval applies only to
that prerequisite document; P4-T7 remains optional, incomplete, corpus-gated, and
NO-GO/deferred, with no feasibility verdict.
