# Phase 2P — Creative Quality, Measured (M2)

_Goal: the LLM's judgment can actually reach the light (widened channel), the
analysis substrate is upgraded to model-grade truth (MIR + stems), and every run is
scored by the vision-eval harness — then the deterministic-vs-LLM comparison runs as
a validation gate inside the committed direction. Proposal M2; D1/D4/D6/D8/D10/D11 +
parts of D2._

**Exit criteria:** plan schema v2 rendered end-to-end (intensity/color/shutter/gobo
intents + lyric MomentCues); MIR A/B decided on golden fixtures; stems stage cached
and feeding features; vision-eval harness scores any sequence for ~$0.15; the
three-arm comparison verdict is recorded with human spot-checks; model retarget +
structured outputs done before the Dec 2026 retirements.

## Lanes

- **Lane S (schema/channel, serial)**: T1 → T2 → T3 → T4 (the widened channel).
- **Lane M (analysis substrate, parallel)**: T7 → T8 (stems, MIR) — merges before T13.
- **Lane E (evaluation harness, parallel)**: T5 → T6 (render client, judge).
- **Lane P (platform, parallel)**: T10 → T11 (retarget, structured outputs).
- **Lane W (workflow)**: T12 (injection v1) after T4.
- **Gate**: T9 (judge feedback repair) in `agents/shared` — after T1, before T13.
- **Finale**: T13 (three-arm comparison) after all lanes.

## Tasks

| ID | Title | What (summary) | Evidence | Deps | Executor | Verifier |
|---|---|---|---|---|---|---|
| P2P-T1 | Plan schema v2 | Extend `PlanSection` with typed intents: categorical intensity (ONE enum, actually wired — `Intensity` vs `IntensityLevel` unification), color intent (palette role / explicit cue), shutter/gobo events, lyric MomentCue references, optional segmentation; DELETE the 20 verified-dead solicited fields; prompts updated (render `recommended_sections` — loaded-but-never-rendered today); schema stays strict-structured-outputs-compatible (all-required, no top-level unions). | CF-3, P3-F12/F14, P4-F17, D1 | P1P merge | opus | opus |
| P2P-T2 | Renderer resolves schema v2 | Template layer gains parameterized channel support (~300 LOC mirroring the Dimmer family — export layer verifiably needs zero changes); vocabulary resolution wired (the renderer imports it for the first time); intents → curves/DMX with fixture-default fallbacks. | P4-V1 extension, P5-V1 | P2P-T1 | opus | opus |
| P2P-T3 | Data-first template loader | Templates loadable from data (registry accepts JSON template docs alongside the 37 Python builtins; a converter emits data-form from Python-form); progressive migration path — no big-bang re-authoring; convergence note: a data-first MH template is structurally a recipe (one catalog, two renderers, later). | D1 design, P4 template census | P2P-T2 | opus | opus |
| P2P-T4 | Lyric MomentCues wired | Fix the blind wiring (prompt reads `narrative_arc`/`key_moments` — fields that DO NOT EXIST on `LyricContextModel`; extra="forbid" guarantees it): define MomentCue on the lyrics model, render real fields into the MH planner prompt, thread cues into schema-v2 events; fix few-shot delivery (filename bug + CONVERSATIONAL drop — currently no agent ever receives examples). | CF-4, P3-F5/F13 (airtight) | P2P-T1 | opus | opus |
| P2P-T5 | Preview render client | Python client for the xLights automation API: `loadSequence→renderAll→exportVideoPreview→closeSequence` (command verified implemented; upstream BatchVideoExport.lua is the reference); windowed-instance management on macOS; fseq-compare (`--fseqcmp`) as the CI-tier deterministic check (video export can't run headless). | D11 research (verified) | P1P-T11 | sonnet | opus |
| P2P-T6 | Vision judge + deterministic sync metrics | ffmpeg frame sampling (2–4 fps / contact sheets) → gpt-5-mini rubric judge (4 categories adapted from AutoMV: musicality-by-proxy, coordination, palette coherence, variety/pacing) fed WITH Twinklr's timestamped structure as text; deterministic sync scorer (beat grid vs effect timestamps — the VLM never judges sync, per Omni-Judge warning); calibration protocol vs human spot-checks; ~$0.13–0.15/song budget enforced. | D11 research, SF-4 | P2P-T5, P1P-T10 | opus | opus |
| P2P-T7 | Stems stage (D8) | `demucs` 4.1.0 (maintained repo; MIT; torch unpinned; MPS auto) as an opt-in cached analysis stage; per-stem features: drum-stem onsets → accent/beat confidence, bass energy → build/drop truth, vocal-stem presence → replaces the (now-fixed) full-mix detector as lyrics/WhisperX gate; cache key = audio hash + model. | D8 research (verified) | P1P-T8 | sonnet | opus |
| P2P-T8 | MIR A/B + adoption (D10) | Integrate `beat-this` (beats+downbeats) and All-In-One (`all-in-one-mlx` on Apple Silicon) behind the BeatGrid interface; A/B against current DSP on golden fixtures + the new ground-truth assertions; adopt per the gate (keep custom energy/builds/tension regardless); one model-derived rhythmic/structural truth then feeds ALL grid consumers (completing what P1P-T4 started at the consumer level). Record the decision either way. | D10 research (verified), P2 §7 | P1P-T4, P1P-T8 | opus | opus |
| P2P-T9 | Judge feedback repair (D4) | KEEP iterative judging (flipped default): give the judge memory of its own prior verdicts (the entire `judge_context_builder` hook is dead and its signature can't carry feedback — needs the orchestrator to close over verdict history); ONESHOT schema-repair shows the model its failing output (today it's a blind full-cost resample); wire-or-fix `success_threshold` (fully threaded, annihilated by hardcoded 7.0/5.0) and `max_iterations=0` (documented value crashes). | P3-F7/M-A/M-B/M-D, D4 | P2P-T1 | opus | opus |
| P2P-T10 | Model retarget (D6) | `gpt-5.6-sol` planners/profile/lyrics, `terra` judge, `gpt-image-2` (assets, ahead of the 2026-12-01 retirement), explicit `reasoning.effort` per role (5.6 defaults medium — silent cost/latency change otherwise); consolidate the 29 hardcoded model sites into wired config (most AgentConfig fields are currently unwired — wiring is the task); includes P1K-T5's relocated call sites. Cache-safe (model IDs already in keys). | D6, M1 modernization, P1-F15 | P1P-T9 | sonnet | opus |
| P2P-T11 | Structured outputs (D6) | One-call `json_object`-on-5.6 probe, then migrate to strict `json_schema` / `responses.parse` with Pydantic models (constraints: all-required fields, no top-level unions — P2P-T1 designed for this); repair loop shrinks to refusal/truncation handling; JSON-parse failures get retry parity (today: zero retries and pipeline death for the commonest failure mode). | M2 modernization, P3-M-G | P2P-T10 | opus | opus |
| P2P-T12 | Live injection workflow v1 (D2) | `getModels` → plan against the user's real layout → `addEffect` into the open sequence; per-section regenerate command (the hobbyist iteration loop); shares the T5 client; document the unauthenticated-local-port caveat. | D2 (promoted), M6b research | P2P-T2, P2P-T5 | opus | opus |
| P2P-T13 | Three-arm comparison | Build the deterministic selector arm (energy_range ∩ section-energy + `recommended_sections` join + variety constraints — annotations verified discriminating); run deterministic / full-LLM / macro-ablated over the song set; scored by T6 every run + human spot-checks; record the D1 standing-default verdict in the proposal and decision record. | D1, CF-3, Stage 2 §4 | ALL lanes | opus | opus (+ owner reads verdict) |

## Notes for spec authors

- T1 and T9 both touch `agents/shared`+schemas: T1 lands first; T9 rebases.
- T8's A/B criteria must be numeric and pre-committed (beat F1 / downbeat F1 /
  section-boundary tolerance on the fixture set) — no post-hoc judgment.
- T13's spec includes the experiment protocol (N songs, arms, seeds, cost cap, what
  "parity" means) — copy the standing-default language from D1 verbatim.
