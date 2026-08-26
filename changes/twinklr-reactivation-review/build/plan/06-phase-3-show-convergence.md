# Phase 3 — Show Convergence (M3)

_Goal: part 2 ships — display choreography from learned grammar, coordinated with
moving heads by the shared macro contract, delivered through the same ladder.
Proposal M3; D3/D13 + P5 display cluster + the apply edge's code half._

**Exit criteria:** one command, one song, the user's layout → coordinated MH +
display show importable into xLights (or injected live); the display planner consumes
the tracked catalog + macro arc + layout; evaluation results + human judgments
recorded for display output; assets pipeline optionally enriching Pictures effects.

> **Sequencing exception — 2026-08-16:** P3-T1/P3-T2/P3-T3 are merged and independently
> verified at `5eebcb2`, `5365f70`, and `33cce57`. The owner accepted P3-T4's exact
> contract/invariants and AC2 amendment; independent offline/code reviews approved the
> implementation and general `$ref` remediation, integrated at `558153c`. P3-T4 live
> acceptance remains open after one HTTP 400 `invalid_json_schema`; no retry/fallback
> occurred and usage was unavailable, so `$1.660000` remains committed. On 2026-08-26
> the owner authorized exactly one second audited request under a new `$3.32` cumulative
> cap. Attempt 2 made one provider request and received HTTP 400 because `temperature`
> is unsupported by `gpt-5.6-sol`; no retry/fallback/logical request/schema repair or
> usage metadata occurred. Both `$1.660000` reservations remain committed, the
> two-attempt cap is exhausted, no third attempt is authorized, and live acceptance
> remains open. Offline capability normalization removes temperature for this model
> without creating another live attempt. The owner subsequently accepted all nine P3-T5
> decisions, and P3-T5 was integrated at `f006468`. P3-T6's remediated offline/code
> candidate received independent standards, specification, and adversarial approval and
> was integrated at `c9620db`. P3-T8's offline implementation was integrated at
> `82438cf`, and P3-T7's independently approved code is included in the current
> integration. Phase 3 now has all eight offline task implementations integrated. P3-T6
> empirical xLights GUI acceptance remains open. The owner authorized P3-T7+ and its
> task-bounded live/paid work on 2026-08-26. All xLights GUI dates/checks remain deferred
> until there is a meaningful, fully working end-to-end show; the gates remain open and
> are not waived. These exceptions do not waive the Phase 1P/2P/2K exits or close P3-T4
> live acceptance.

## Lanes

- **Lane C (composition repair)**: T1 → T2 (display/composition files).
- **Lane W (wiring)**: T3 → T4 → T5 (pipeline/CLI/coordination).
- **Lane X (export unification)**: T6 (formats + both writers) — after T2.
- **Lane A (assets)**: T7 (agents/assets) — independent until T5.
- **Finale**: T8.

## Tasks

| ID | Title | What (summary) | Evidence | Deps | Executor | Verifier |
|---|---|---|---|---|---|---|
| P3-T1 | Composition timing repair | Fix the sub-beat floor + non-inverse `_ms_to_planning_ref` (constant offset of `beat_boundaries[0]` + drift, then floored — every placement can shift a full beat) with the intentional section_start_bar=0 convention preserved; SEQUENCED actually sequences (slot = step_ms, one-line fix verified); TRIM gap harm (short surviving nested neighbours); reset `_layer_blend_modes` per compose. | P5-F1/F2/F12/M2 (verified mechanics) | P2P-T8 (real grid) | opus | opus |
| P3-T2 | Blend modes + effect fallback truth | Restate lane blend-mode wiring so RHYTHM/ACCENT lane modes can actually reach output (structurally impossible today — allocator keys 0/2/4 vs lanes emitting on 6–16); unrecognized effect_type no longer silently renders as `On` — validate against the handler registry at recipe admission AND surface the fallback into WriteResult/trace. | P5-F3 (corrected mechanism), P5-M1 | P3-T1 | opus | opus |
| P3-T3 | Display pipeline CLI-reachable | `twinklr display` becomes the canonical branch-only display command: layout from the user's rgbeffects, catalog from the tracked store, FE context bundle threading (the apply edge's code half — group planner context shaping already works when fed); remove the demo-script-only status. | Edge 2, P6/P5 wiring evidence | P1K-T3, P2K-T4 | opus | opus |
| P3-T4 | Macro structured contract (D3) | Slim MacroPlan to the fields both back-ends consume, as TYPED inputs to section planning (today: prose-only into one prompt); cross-element coordination fields (call-response pairs, focal roles, palette continuity) defined with the display planner as first consumer and MH schema-v2 as second. | D3, P3-F1 (CRITICAL), CF-3 | P2P-T1 | opus | opus |
| P3-T5 | MH + display coordination | Additive `twinklr show`: one show plan drives both renderers while branch-only `run`/`display` remain; shared macro arc and BeatGrid; section-level coordination verified in normalized XSequence + trace golden output (MH sweep + megatree spiral + arch chase at the drop). | D3, program M3 | P3-T3, P3-T4 | opus | opus |
| P3-T6 | Unified export core | Harvest display's dedup registries as THE export core (P3-T5 already pulled forward unconditional positional seeding/preservation); one emitter, one layer policy, one stamp/grid policy, MH dedup, shared trace, and file/injection delivery. | P5-F4/F15/M3/M4, CC-6 | P3-T2 | opus | opus |
| P3-T7 | Assets revival (D13) | Reactivate `agents/assets` for Pictures-effect imagery on `gpt-image-2`: fix the verified defects (non-atomic error-swallowing catalog = the real re-bill mechanism; cross-song reuse-key collisions; gather without return_exceptions discarding paid siblings); provider-framework integration; per-run spend cap + cache. | D13, P3-F28/M-J/K/L | P2P-T10 | sonnet | opus |
| P3-T8 | Show-level evaluation | Vision-eval harness extended to display/combined shows (rubric gains coordination-across-parts criteria); first recorded combined-show evaluation + human judgment; results flow into the loop (D5's fourth arm begins). | D11, D5(d) | P3-T5, P2P-T6 | sonnet | opus |

## Implementation status — 2026-08-26

- P3-T1 through P3-T8 offline task implementations are integrated at the commits recorded in the campaign handoff;
  P3-T6 is integrated at `c9620db` after independent standards, specification, and
  adversarial approval offline/in code.
- P3-T4 live acceptance remains open after two failed audited requests. Attempt 2 was
  terminal HTTP 400 unsupported `temperature`, with one provider request and no retry,
  fallback, logical request, schema repair, or usage metadata. `$3.320000` is committed,
  the two-attempt cap is exhausted, and no third attempt is authorized. The offline
  model-capability remediation does not reopen that boundary.
- P3-T6 empirical xLights GUI acceptance remains open, with its date deferred until a
  meaningful end-to-end show is fully working. P3-T7+ and task-bounded live/paid work
  are owner-authorized. P3-T7's one-request/no-retry image proof passed with a valid
  1024×1024 PNG, a zero-call scoped cache replay, and measured cost `$0.00622`; its
  terminal sealed ledger forbids another attempt. P3-T8's
  preview/live-judge/human/calibration evidence remains deferred. The
  Phase 1P/2P/2K empirical exits remain open and are not implied by P3-T6 integration.

## Notes for spec authors

- T1/T2 mechanics MUST be copied from the corrected verifier versions in
  `verification.md` (both had inverted mechanisms in the original phase doc).
- T4 is design-bearing and shared with 2P's schema work — the spec defines the
  contract ONCE; MH and display specs reference it.
- T7 keeps `enable_assets`-style gating but documents the real activation path
  (the old flag was gated off everywhere; the paid path was a demo script's --live).
