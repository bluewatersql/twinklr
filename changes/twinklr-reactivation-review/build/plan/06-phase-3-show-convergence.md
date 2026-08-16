# Phase 3 — Show Convergence (M3)

_Goal: part 2 ships — display choreography from learned grammar, coordinated with
moving heads by the shared macro contract, delivered through the same ladder.
Proposal M3; D3/D13 + P5 display cluster + the apply edge's code half._

**Exit criteria:** one command, one song, the user's layout → coordinated MH +
display show importable into xLights (or injected live); the display planner consumes
the tracked catalog + macro arc + layout; evaluation results + human judgments
recorded for display output; assets pipeline optionally enriching Pictures effects.

> **Sequencing exception — 2026-08-16:** the owner explicitly authorized P3-T1 and then
> P3-T2 before the outstanding Phase 1P/2P/2K empirical exits. P3-T1 is merged and
> independently verified at `5eebcb2`; P3-T2 is merged and independently verified at
> `5365f70`. This exception does not waive those exits
> and does not authorize P3-T3 or any later Phase 3 task.

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
| P3-T3 | Display pipeline CLI-reachable | `twinklr` gains the display/show command: layout from the user's rgbeffects (or `getModels`), catalog from the tracked store, FE context bundle threading (the apply edge's code half — group planner context shaping already works when fed); remove the demo-script-only status. | Edge 2, P6/P5 wiring evidence | P1K-T3, P2K-T4 | opus | opus |
| P3-T4 | Macro structured contract (D3) | Slim MacroPlan to the fields both back-ends consume, as TYPED inputs to section planning (today: prose-only into one prompt); cross-element coordination fields (call-response pairs, focal roles, palette continuity) defined with the display planner as first consumer and MH schema-v2 as second. | D3, P3-F1 (CRITICAL), CF-3 | P2P-T1 | opus | opus |
| P3-T5 | MH + display coordination | One show plan drives both renderers: shared macro arc, shared BeatGrid, section-level coordination verified in golden output (e.g., MH sweep + megatree spiral + arch chase at the drop, from one plan). | D3, program M3 | P3-T3, P3-T4 | opus | opus |
| P3-T6 | Unified export core | Harvest display's dedup registries as THE export core (seeded from any pre-existing EffectDB — same fix as the wholesale-replace defect); one emitter, one stamp/grid policy (today: 2024.10 vs 2024.01, 50ms vs 20ms, MH unquantized); both delivery paths (file + injection) share it. | P5-F4/F15/M3/M4, CC-6 | P3-T2 | opus | opus |
| P3-T7 | Assets revival (D13) | Reactivate `agents/assets` for Pictures-effect imagery on `gpt-image-2`: fix the verified defects (non-atomic error-swallowing catalog = the real re-bill mechanism; cross-song reuse-key collisions; gather without return_exceptions discarding paid siblings); provider-framework integration; per-run spend cap + cache. | D13, P3-F28/M-J/K/L | P2P-T10 | sonnet | opus |
| P3-T8 | Show-level evaluation | Vision-eval harness extended to display/combined shows (rubric gains coordination-across-parts criteria); first recorded combined-show evaluation + human judgment; results flow into the loop (D5's fourth arm begins). | D11, D5(d) | P3-T5, P2P-T6 | sonnet | opus |

## Notes for spec authors

- T1/T2 mechanics MUST be copied from the corrected verifier versions in
  `verification.md` (both had inverted mechanisms in the original phase doc).
- T4 is design-bearing and shared with 2P's schema work — the spec defines the
  contract ONCE; MH and display specs reference it.
- T7 keeps `enable_assets`-style gating but documents the real activation path
  (the old flag was gated off everywhere; the paid path was a demo script's --live).
