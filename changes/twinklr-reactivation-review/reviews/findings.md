# Normalized Findings Register

_Consolidated from the seven VERIFIED phase reviews (2026-08-13, baseline `aa8d325`).
One entry per root cause; `Sources` lists the constituent phase-finding IDs (full
evidence, reproducers, and verifier verdicts live in reviews/phases/*.md and
reviews/verification.md — not duplicated here). All entries: Finding status =
ACCEPTED (adversarially verified by a non-author); Observation date 2026-08-13;
Baseline SHA aa8d325. Severity: CRITICAL/HIGH/MEDIUM/LOW/INFO. Confidence: CONFIRMED
unless noted. Disposition: KEEP/FIX/SIMPLIFY/MODERNIZE/REPLACE/REMOVE. RM-x = feeds
that remediation-roadmap item._

## Critical / product-defining

| ID | Title | Sev | Sources | Disposition → RM |
|---|---|---|---|---|
| CF-1 | Movement intensity overwritten — all output renders SMOOTH; existing test pins the defect; naive fix KeyErrors 27/29 patterns; must land with frequency-amplitude fix | CRITICAL | P4-F1/F1a/M4/M6 | FIX → RM-1.1 |
| CF-2 | Three misaligned time grids (planner nominal-floor, renderer average, real downbeat tracks); spans phases 3+4; snap helpers have zero callers | CRITICAL | P4-F2, P4-M3 | FIX → RM-1.1 |
| CF-3 | LLM→renderer channel is two strings wide; macro plan reaches renderer only as prompt prose; 20 dead solicited fields; categorical vocabulary never imported by renderer (refutes docs + decision record) | HIGH (strategic) | P3-F1/F12, P4-F17/F18/F23 | PROJECT DECISION → RM-2.* |
| CF-4 | Shipped planner is lyric-blind (prompt reads nonexistent fields; extra=forbid); lyrics agent output has no sink | HIGH | P3-F5 | FIX → RM-1.4 |
| CF-5 | `.xsq` template content loss on every shipped run (required `--xsq` + extra=ignore + full XML regeneration); generate-fresh branch never executed and self-fatal; layer-0 interleaving + EffectDB wholesale replace corrupt template-sourced sequences | HIGH | P5-F4/F5, V-contract | REPLACE contract → RM-2.2 |
| CF-6 | Renderer output-corruption cluster: short sections render nothing (34/1/2 census), narrative templates play one step, 2× overrun, calibration annihilated, dimmer floors dropped, BLACKOUT full-brightness inversion, preset space ≈67, snap-back tails | HIGH | P4-F4/F5/F6/F8/F9/M1/M2/M5 | FIX → RM-1.1 |
| CF-7 | Exporter zero-fills all 16 DMX channels; shutter closed=0 vs repo's own open=255 default (zero readers); possible dark shows (fixture-conditional; test spec ready) | HIGH | P4-F3, P5-V1 | FIX → RM-1.2 |

## Cross-cutting classes

| ID | Title | Sev | Sources | Disposition → RM |
|---|---|---|---|---|
| CC-1 | Dead-configuration class (~20 members incl. token budget ×3 paths, judge_agent, inert success_threshold, crashing max_iterations=0, checkpoint, logging, cancel_token, channel/fixture fields, template defaults, CLI hardcodes over live config) — user guide unreliable as behavior description | HIGH (class) | P7-M2, P1-F5..F8/F10/F15/F19, P3-F2/F6/M-A/M-B, P4-F15/F16/M1, P2-M11/M14 | FIX or REMOVE per member → RM-1.5, RM-5.2 |
| CC-2 | Authored-for-nonexistent-entry-points class: make build (+empty wheels+tree pollution), 4 phantom test targets, deleted coverage script, 60 tests for six nonexistent scripts/build tools, phantom canonical build script in docs, deleted checkpoint writer | HIGH (class) | P7-F2/F4/F5, P1-F23, Stage 4, P6-F3 | REMOVE/rebuild-from-intent → RM-0.2, RM-1.6 |
| CC-3 | Silent-degradation class: metadata 100% failure swallowed (tests certify wrong contract), HPSS collapse, validator computed-and-discarded, effect-type→On fallback, failed-LLM-calls unlogged, wave failure discards siblings | HIGH (class) | P1-F1/F2/M1, P2-F1..F3/M8, P5-M1(F8), P3-M-E | FIX + observability spine → RM-1.3, RM-4.1 |
| CC-4 | Token/cost instrumentation broken on shipped path: attribution race (one defect, confirmed twice), budget no-op end-to-end, per-call repair resampling blind in ONESHOT, retry amplification ≤9 | MED-HIGH | P1-F27=P3-F24, P1-F13-adjacent, P3-F6/M-D/M-F | FIX → RM-1.4 |
| CC-5 | Cache identity: random session UUID defeats reuse (deliberate capability unused); CWD-relative root; prompt content absent from keys (retarget safe; prompt edits stale-serve once reuse fixed) | MED-HIGH | P1-F4/M3, fingerprint addendum | FIX as one change → RM-1.4 |
| CC-6 | Duplication debt: 2 OpenAI clients/4 retry stacks, 2 configure_logging, 3 type-check configs (core linted WEAK — empirically confirmed), 2 fresh emitters (stamp+grid conflict; MH unquantized), 2 XSQ writers (dedup asymmetry; harvest+seed), triplicated fallbacks, v1/v2 straddles | MEDIUM (class) | P1-F12/F14/F20/F21/F25, P5-F15/M3, P2-F21/F23, P6 v1/v2 | SIMPLIFY → RM-5.1 |
| CC-7 | Test-system integrity: inverted mass, wrong-contract mocks (3 proven), zero ground-truth assertions (tempo/beat/key), zero round-trip tests, 112 structural failures from clean checkout, NLTK network dep | HIGH | P2-F24/F25, P7-F7/F15, P4-F22, Stage 4 | FIX → RM-0.2, RM-1.6 |
| CC-8 | Determinism violations in "deterministic" layers: 2 LLM sites outside agent framework (one hardcodes gpt-4o-mini — retarget-grep blind spot), unseeded shuffle, uuid corpus identity defeating store idempotency | MED-HIGH | P6-M1/M2, P3-M-C | FIX/EXTRACT → RM-3.1, RM-5.3 |
| CC-9 | Trust boundaries: shipped lyric/metadata prompt-injection hops; LLM-authored expr/effect_type boundaries (mitigated); settings-string injection; unbounded text fields; sole-defense cache containment | MEDIUM | P3-F18/F19, P5-F6/F7/F14/M1, P2-F20, P1-S2 | FIX → RM-1.3, RM-4.2 |

## Subsystem findings (consolidated)

| ID | Title | Sev | Sources | Disposition → RM |
|---|---|---|---|---|
| SF-1 | Audio DSP live defects: vocals hop-length drift (~6-8s misalignment every run), builds merge drops builds, trim-offset guard misses energy array, flatness hop mismatch, hardcoded 4 beats/bar | MED-HIGH | P2-M2/M4/M5/M6/M7 | FIX → RM-1.3 |
| SF-2 | Lyrics resolution order inverted by analyzer parallelization: LRCLib/Genius structurally skipped; ASR outranks synced lyrics; double resolution when WhisperX off; no vocal gate on transcription | HIGH | P2-M1/F14 | FIX → RM-1.3 |
| SF-3 | Metadata enrichment fails 100% (httpx.Response into dict parsers; both clients; MB unreachable until AcoustID fixed — limiter must land in same change) | HIGH | P1-F1/F2, P2-M3/F13 | FIX → RM-1.3 |
| SF-4 | Evaluation harness: writer deleted (restorable ~10 lines, schema drift trap), CLI unbridged, ComparisonReport zero producers/tests, measures self-consistency only, no result ever committed | HIGH (enabler) | P6-F3/F4 + verifier archaeology | FIX FIRST → RM-1.6 |
| SF-5 | Corpus 4-pack: unreachable from product; uuid identity; license/rights untracked for vendor mining (prospective gate); learned taxonomy is weak-supervision circular; style_transfer + 3/4 of active_learning orphaned | MEDIUM (strategic) | P6 all | EXTRACT → RM-5.3, gate RM-G2 |
| SF-6 | Display composition defects (deferred subsystem): sub-beat floor + non-inverse mapping, SEQUENCED continuous-light, blend modes structurally lost, TRIM gaps, unreset state | HIGH-in-subsystem | P5-F1/F2/F3/F12/M2 | DEFER (documented) → RM-5.4 |
| SF-7 | Engineering system: no quality-gate CI; validate mutates; packaging nonfunctional (empty wheels + pollution); mypy gate = one loop-variable rename; ruff core-config weakness; .env illusion; no LICENSE ever | HIGH | P7 all, P1-F20..F23, Stage 4, P6-M3 | FIX → RM-0.* |
| SF-8 | Docs describe a different system: six-channel claim false; removed LLM-validator documented; user-guide knob table unreliable; phantom paths; "dozens of hours" claim is unsourced marketing provenance | HIGH (docs) | P7-M2/M3, Stage 2 §1, B7 | FIX → RM-5.5 |

## Strengths (KEEP register)

| ID | What | Sources |
|---|---|---|
| ST-1 | Schema/taxonomy auto-injection — zero drift by construction | P3-F35 |
| ST-2 | Judge verdict enforcement (caveat: kills threshold knob — M-A) | P3-F36 |
| ST-3 | BeatGrid sole-timing-authority design (display side) | P5/P4 |
| ST-4 | Atomic cache commit; FS abstraction (containment must become protocol contract) | P1-S1/S2 narrowed |
| ST-5 | Display writer dedup registries + trace sidecar (harvest target) | P5-F15/F18 |
| ST-6 | Five deterministic auto-repair passes (display planner path) | P3-F10 |
| ST-7 | Existing 587-LOC .xsq validator with all-zero/channel cross-checks | P4-M8/F22 |
| ST-8 | timeline.py timing tracks — CLI-reachable, correct, best-tested; `.xtiming` MVP candidate | P5 + M6b |
| ST-9 | DDL-as-data + identifier allowlist + Protocol DI (feature store) | P6 |
| ST-10 | Ingestion safety (zip-slip, XXE, nested-archive cycles) | P6-M5 |
| ST-11 | Audio DSP architecture + Foote novelty correctness (reference-loop verified) | P2 §7/§9 |
| ST-12 | recipe_builder staged-only human-promotion design | P6 |

## Rejected / reclassified during verification (traceability)

P2-F17 (NaN key confidence — mechanism didn't exist; → INFO weak-test note);
P3-F23's CLI-gate claim (anthropic runs end-to-end); P3-F28's re-bill mechanism
(replaced by catalog mechanism); P5-F3's contamination mechanism (inverted →
structural loss); P6's determinism headline (narrowed to traced path); P6-F5
HIGH→MEDIUM (prospective gate); P2-F13 live-violation → latent (with sequencing
trap); two P4-F20 deletion rows (imported — unreachable-at-runtime, not deletable
as-is); P1-F29's headline (FSCache IS covered, wrong package); "35/37 cycle_bars"
census (34/1/2). Full verdicts in verification.md.
