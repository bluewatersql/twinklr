# Phase 4 — Compounding (M4)

_Goal: modern platform, retired debt, honest docs, optional capabilities. Nothing
here blocks the product; everything here reduces friction for whatever comes next.
Proposal M4; D7/D12 + recorded debt-sequencing constraints._

**Exit criteria:** modern ML chain on Python 3.13; dead tail removed without
breaking anything (sequencing constraints honored); user guide describes only wired
behavior; local-provider option available.

**Execution status (2026-08-26):** P4-T1, P4-T2, and P4-T3 are independently verified
and integrated (**3/7**). P4-T2's implementation and redirect-hardening remediation are
integrated through `3765bd9`/`40e8e55`, but its real Ollama schema smoke remains
unclaimed pending explicit local opt-in. P4-T3 is integrated at `bf6bba5`. Phase exit is
not satisfied; P4-T4 is next. Exact evidence remains single-owned by the
[P4-T2](../specs/phase-4-compounding/P4-T2-local-provider-option.md) and
[P4-T3](../specs/phase-4-compounding/P4-T3-dead-tail-retirement-wave-1.md) task specs.

## Tasks

| ID | Title | What (summary) | Evidence | Deps | Executor | Verifier |
|---|---|---|---|---|---|---|
| P4-T1 | ML chain + Python bump (D7) | One coordinated change: delete the orphaned diarization module FIRST (pyannote-4.x breakage concentrates there), then torch/torchaudio 2.8.x + whisperx 3.8.6 + pyannote 4.x + Python 3.12→3.13 ⚖; update the constraint memory; watch item: torchaudio maintenance wind-down (TorchCodec migration) — prefer deps that dropped it. | D7, M3 modernization | Phase 2P merged | opus | opus |
| P4-T2 | Local provider option (D12) | Provider config for Ollama via OpenAI SDK `base_url`; structured outputs route via `/v1/chat/completions` `response_format` (the `/v1/responses` gap is documented); target models benchmarked against OUR schemas (`qwen3.5:27b` / `granite4.1:30b` / `nemotron-3.5-lightning` class); offline-December smoke test. | D12 research | P2P-T11 | sonnet | opus |
| P4-T3 | Dead-tail retirement wave 1 (safe) | Remove with recorded sequencing honored: migrate FSCache tests to `tests/unit/caching/` FIRST then delete the sync-adapter; unwire-then-delete the two "unreachable at runtime but imported" curve rows (modifiers, providers/native — deleting without unwiring breaks the build); diarization goes in P4-T1; orphaned audio modules (genre classifier, stale context builders + the phantom-schema conftest fixture, dead Section model, dead tempo-changes twin incl. its public re-export), display compat converters, `SequenceAnalyzer` chain, `simplify_rdp`. | P1-F29/F31, P4-F20 (corrected), P2/P5/P6 dead inventories | Phases 1P/3 merged | sonnet | opus |
| P4-T4 | Duplication collapse | One OpenAI client + one retry policy (SDK `max_retries` explicit — kills the ≤9-requests amplification); one `configure_logging` (wire or delete `AppConfig.logging`); conversation-store eviction; httpx client lifecycle (aclose); scipy/penalty triplication collapse. | CC-6, P3-M-F/M-H, P2-M10/F21/F23 | P2P merged | sonnet | opus |
| P4-T5 | Dead-config final sweep | Every remaining CC-1 member is wired-with-a-behavior-test or deleted-with-docs — no third state; acceptance = a generated knob-inventory test asserting every documented config key has an observable effect. | CC-1, RM-1.5 | P1P/P2P/P3 wiring done | sonnet | opus |
| P4-T6 | Documentation truth pass | User guide regenerated from wired config only; six-channel claim now true (post schema-v2) or corrected; architecture docs match the shipped loop; phantom paths removed; "dozens of hours" replaced by measured numbers from the eval harness; scripts/ triage (promote/delete per P7 table). | SF-8, P7-M2/M3, measured data | P4-T5 | sonnet | opus |
| P4-T7 | MH-idiom mining exploration (optional) | Feasibility spike: extend the miner to DMX moving-head sequences in vendor packs (the deleted-history artifact proves they exist); if propensity/idiom extraction works for MH, part 1 joins the knowledge loop (one catalog, two renderers, completed). Time-boxed; outcome = a decision memo, not a feature. | M4, D5 convergence note | P2K-T2 | opus | opus |

## Notes for spec authors

- T3's spec must enumerate every deletion with its verified zero-callers evidence AND
  its sequencing constraint — this is where "actionable-and-wrong" F20-style rows
  would do damage; copy the corrected labels.
- T5's knob-inventory test is the phase's real deliverable: it makes dead config a
  CI-detectable class forever.
- T7 is deliberately last and optional — it must not leak scope into earlier phases.
