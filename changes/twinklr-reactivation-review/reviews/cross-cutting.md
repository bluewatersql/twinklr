# Cross-Cutting Synthesis (Stage 5)

_Authored 2026-08-13 by the orchestrator from the seven VERIFIED phase reviews,
Stage 2, Stage 4 runtime baseline, Stage 6 modernization, and the full verification
record. Every claim below is backed by an adversarially verified finding; source IDs
cite phase docs (P1-P7) and verification.md. Baseline `aa8d325`._

## 1. Is this one coherent system?

No. The repository contains **three products and a shared audio front-end**, of which
exactly one ships: the moving-heads path (~26k LOC reachable from `twinklr run`). The
display pipeline (8.3k), the corpus/feature-engineering stack (20.5k + profiling
3.9k), and the evaluation harness (3.5k) are complete, separately competent, and
disconnected (DISCONNECT). The documentation describes the union as if it were the
product; the runtime delivers the intersection. This is the single largest gap between
claim and reality and it shapes every other conclusion.

Classifications: display = DISCONNECT (deliberate DEFER per Stage 2, confirmed);
corpus 4-pack = DISCONNECT + PARTIAL_MIGRATION (extract, per phase 6 verification);
evaluation harness = DEAD_PATH with a **deleted** writer (restoration ~10 lines,
schema-drift trap documented — P6-F3).

## 2. The central architectural finding

The accepted decision "LLMs plan intent; deterministic code implements precision" is
**implemented in name only on the shipped path** (IMPLEMENTATION_DIVERGES_FROM_INTENT,
multiply verified):

- The renderer consumes five plan fields — effectively `template_id` (37 options) +
  `preset_id` (~67 distinguishable outcomes after P4-F8's collapse) (P4-F23, V2).
- The macro planner's entire output reaches rendering only as prose in a downstream
  prompt (P3-F1, CRITICAL); its cost is 2–6 gpt-5.2 calls per song.
- The lyrics agent — the one irreplaceable LLM use — is blind-wired: the MH planner
  prompt reads fields that do not exist on the lyrics model (`extra="forbid"` makes
  injection impossible), so the shipped planner is lyric-blind (P3-F5, airtight).
- The audio-profile agent re-derives values printed into its own prompt; its
  "most important" output is never passed onward (P3-F3).
- 20 solicited schema fields are dead; few-shot examples are never delivered; the
  judge has no memory of its own prior verdicts; ONESHOT schema-repair never shows the
  model its failing output (P3-F12/F13/F7/M-D).
- `recommended_sections` — the join key that would make template selection a
  deterministic table lookup — is loaded, carried, serialized, and never rendered
  into the prompt (P4-V3; annotations verified discriminating across all 37).
- The categorical vocabulary (46 enums/253 members) **never reaches the shipped
  renderer**: zero imports; `Intensity` and `IntensityLevel` are unrelated enums with
  no converter; `categorical_resolver` is dead (P4-F17/F18, REFUTES the architecture
  docs and the decision record's description of reality).

Verdict: the two-string-wide channel, not the model choice, is the binding
constraint. Cost (~$0.25/song verified pricing) is not. The strategic fork — widen the
channel (templates exposing color/gobo/shutter + parameters) vs. drop to a
deterministic selector — is a PROJECT DECISION gated on the three-arm experiment
(Stage 2 §4), which itself is **blocked by defects catalogued below**.

## 3. The renderer: the claimed moat, and its condition

Keep the subsystem; retract the "tested" adjective (phase 4 + verifier, joint
verdict). The compile/export math is sound where wired, and the template annotation
table is genuinely discriminating — the deterministic-selector option is feasible. But
an adversarially verified cluster of output-corrupting defects means **current output
does not represent the system's design intent**:

| Defect | Effect | ID |
|---|---|---|
| Intensity overwritten unconditionally | every movement renders SMOOTH; a test PINS the defect | P4-F1 (CRITICAL) |
| Three misaligned time grids (planner floor → renderer average → real downbeat tracks) | effects drift vs beat markers; section starts quantized up to ~2s | P4-F2 + P4-M3 (CRITICAL, spans phases 3+4) |
| Scheduler: sections < cycle_bars render nothing | 1-bar sections: ALL 37 templates emit nothing; 1–3-bar: 35/37 | P4-F4 (HIGH) |
| 2 narrative templates render only their loop step; 1 overruns 2× | structure loss, overlapping layer-0 effects | P4-F5/F6 (HIGH) |
| Calibration arithmetically annihilated (center_offset always 0.5) | emitted DMX can exceed calibrated mechanical range | P4-F9 (HIGH) |
| Template dimmer floors never read | dimmers drive to 0 instead of floor 60 | P4-M1 (HIGH) |
| BLACKOUT templates render full brightness under non-MODERATE presets | plan-triggerable inversion on drop sections | P4-M2 (HIGH) |
| Exporter zero-fills channels 1–16; shutter closed=0; repo's own default says open=255, zero readers | possible dark shows; contradicts the repo's declared intent | P4-F3/P5-V1 (HIGH, fixture-conditional; test spec written) |
| End-of-segment full-excursion snap-back; frequency halving doubles excursion | inter-step jumps; SLOW/SMOOTH intent inverted | P4-M5/M6 (MEDIUM) |

**Consequence for sequencing (load-bearing):** the LLM-vs-deterministic A/B cannot
measure anything at baseline — both arms render through the same broken wiring, and
the experiment's instrumentation is additionally blocked by the token-attribution race
(P1-F27=P3-F24, one defect confirmed twice), the inert `success_threshold` (P3-M-A),
and the crashing documented `max_iterations=0` (P3-M-B). **Order: repair the render
path and instrumentation first; then instrument; then decide.** This amends Stage 2's
"instrument first" into "repair-to-measurable, instrument, decide."

## 4. Structural classes (cross-phase, consolidated)

**C1 — Dead configuration / DRIFT (the defining class).** Documented-as-live but
inert or crashing: `token_budget` (three broken paths), `judge_agent`,
`success_threshold` (threaded, annihilated by hardcoded 7.0/5.0),
`max_iterations=0` (crashes), `checkpoint`+`checkpoint_dir`, `AppConfig.logging`,
`cancel_token` (inert), `is_channel_enabled`/`ChannelDefaults`,
`shutter_default`/`color_map`/`gobo_map` (+7 more fixture fields),
`Template.defaults`, `SectioningPreset.context_weights`, `gradient_percentile`,
`enable_*` audio flags (env keys read, flags never flipped), `temperature/max_tokens/
timeout_seconds` for all roles, `AgentSpec.token_budget`, `fixture_count=4` and
`min_pass_score` hardcoded at the CLI over live config. **The user guide is not a
reliable description of behavior — verified as a class (P7-M2 + members from every
phase).** Root cause: config surface written ahead of wiring, no test asserts any knob
changes output.

**C2 — Authored-for-entry-points-that-never-existed / DEAD_PATH.** `make build`
(wrong paths AND empty wheels AND tree pollution — P1-F23 empirical), four
never-existed test targets, deleted coverage script, 60 tests for six nonexistent
`scripts/build/*` tools, `pipeline_guide`'s canonical build script, the deleted
checkpoint writer + its never-called replacement. Remediation posture: delete or
rebuild from intent — not "drift repair."

**C3 — Silent degradation / success-looking failure (UNOWNED_BEHAVIOR).** Metadata
enrichment fails 100% with a swallowed TypeError (tests certify the wrong contract);
HPSS fallback silently collapses harmonic evidence to 0.5 everywhere; the audio
validator's results are computed and discarded at DEBUG (with one check emitting a
spurious warning every run); unrecognized display effect types silently render as
`On`; failed LLM calls produce no log record; wave failure discards completed
siblings' work; heuristic warnings never surface. **There is no error-taxonomy or
observability spine; degradation is an accident of local `except` blocks.** (P1-F1/
P2-M8/P2-F1..3/P5-M1/P3-M-E/P1-M1.)

**C4 — Determinism boundary violations.** Network+ML inside the "deterministic"
audio layer (structural, config-gated only); two LLM call sites outside the agent
framework entirely (`normalization/llm_review.py` hardcoding gpt-4o-mini — any
retarget grep misses it — and recipe generation); unseeded `random.shuffle`;
random-UUID corpus identity that defeats the feature store's own idempotency while
content hashes are computed and discarded (P6-M1/M2). Conversely: the DSP core, the
mining→synthesis chain, and the renderer math are genuinely deterministic.

**C5 — Duplication debt.** Two OpenAI clients with divergent retry/timeout ×
SDK-default retries (≤9 requests/call worst case, P3-M-F); two `configure_logging`;
three type-check configs (ruff resolving the WEAK config for core — P1-F20 CONFIRMED
empirically); two fresh-`.xsq` emitters disagreeing on version stamp AND frame grid
(50ms vs 20ms, with the MH path applying no quantization at all — P5-M3); two
XSQ-writing stacks where only one deduplicates (harvest display's registries into MH,
seeded — P5-F15); triplicated scipy fallbacks and lyrics-penalty logic; v1/v2
straddles (transitions, effect_function, DisplayGraph→ChoreographyGraph with dead
compat converters).

**C6 — Trust boundaries.** Mostly good hygiene, verified: defusedxml on all XML
paths, SecretStr, sandboxed Jinja, correctly configured simpleeval (though its
security test asserts the opposite of production behavior), zip-slip/XXE-safe
ingestion, no in-place mutation of shared arrays. Real gaps: lyric/metadata prompt
injection is live on shipped hops (P3-F18, mechanism corrected); LLM-authored
`expr`/`effect_type` strings are real (mitigated) boundaries; settings-string
injection MEDIUM; unbounded text fields; assets path-traversal (unreachable today);
cache traversal defense exists only as one implementation detail of one filesystem
class (P1-S2 narrowed).

**C7 — Concurrency and resources.** Token attribution race on the shipped wave
(profile+lyrics, shared provider) — blocks cost instrumentation; FAN_OUT ignores
per-stage retry/timeout; conversation store never evicted; httpx pools never closed;
SQLite single-connection with no cross-process story (fine for a single-user tool,
undocumented). Cache: atomic-commit design is good; keys omit prompt content (retarget
safe, prompt edits unsafe — must land prompt-hashing WITH the session-ID fix, which
itself must land with the CWD-relative cache-root fix).

**C8 — Test system.** 4,040 passing tests with inverted mass: 64% of MH test lines on
transitions; compile/export near-zero; parser/exporter zero; **no tempo value, beat
position, or key label ever asserted against known ground truth anywhere**; mocks
certify wrong contracts in three proven cases (metadata clients, F1's pinning test,
simpleeval test); 112 of 120 failures are structural (gitignored corpus data +
nonexistent scripts); unit tests require a live NLTK download. The suite measures
self-consistency, not correctness — mirroring the eval harness, which measures
renderer self-consistency, not show quality, and has never had a committed result.

## 5. What is genuinely strong (verified KEEP list)

Schema/taxonomy auto-injection (zero drift by construction); judge verdict
enforcement (with the M-A caveat that it also kills the threshold knob); BeatGrid as
sole timing authority (display side); atomic two-file cache commits; DDL-as-data +
SQL-identifier allowlisting; Protocol-based DI in the feature store; the display
writer's dedup registries + trace sidecar (the reference implementation for the
export contract); the display path's five deterministic auto-repair passes; the
existing 587-LOC `.xsq` validator (wire it, don't rewrite it); `timeline.py` timing
tracks (CLI-reachable, correct, best-tested formats file — the `.xtiming`-only MVP
candidate); audio DSP core architecture (KEEP with three named correctness fixes);
ingestion safety; recipe_builder's staged-only/human-promotion design.

## 6. Subsystem dispositions

| Subsystem | Disposition | Basis |
|---|---|---|
| Audio DSP core | KEEP + FIX (M2 vocals hop, M4 builds merge, M5 trim guard, M7 beats/bar, M8 logging) | P2 verified |
| Audio enhancement (metadata/lyrics) | FIX as one change-set (client bug + MB limiter + gating inversion + WhisperX gate after vocals fix); SPLIT namespace from DSP later | P1-F1/P2-M1/M3/F14 |
| Agent framework | SIMPLIFY toward the experiment: fix instrumentation blockers; cut macro planner + judges from shipped path pending experiment (PROJECT DECISION); keep runner/injection core | P3 + Stage 2 |
| MH renderer + curves | KEEP + FIX (the §3 cluster, as one golden-tested campaign) | P4 verified |
| formats/xlights | REPLACE input contract (generate-fresh minimal .xsq; parser retained read-only for profiling), MODERNIZE stamps/grid | P5 verified + M6b |
| Display pipeline | DEFER; HARVEST writer dedup into MH now | P5 + Stage 2 |
| Corpus 4-pack (FE/store/recipe_builder/profiling) | EXTRACT to sibling repo (3-file seam); license gate before any mining resumes | P6 verified |
| Evaluation harness | PROMOTE FIRST: restore deleted writer (~10 lines, new schema) + CLI bridge | P6-F3 corrected |
| Engineering system | FIX: minimal CI (check-only), packaging via uv_build, mypy one-liner, structural test repairs, .env decision, LICENSE (PROJECT DECISION) | P7/P1/Stage 4 |
| Dead tail (~4-6k LOC incl. corrected F20 labels) | REMOVE after tests migrate (sequencing constraints recorded) | P1-P6 |

## 7. Accepted-decision conflicts requiring explicit project decisions (Stage 8 inputs)

1. `memories/decisions/llm-plans-intent-renderer-implements-precision.md` — principle
   retained; its description of reality is false for the shipped path (annotated at
   closeout; re-decide after the experiment).
2. Product boundary: template-merge → generate-fresh/import (or `.xtiming` MVP, or
   automation-API injection) — removes a required input; user-facing change.
3. Macro planner removal from the shipped path — overturns documented architecture.
4. Corpus extraction to a sibling repository.
5. Licensing: none exists; blocks distribution regardless of all other work.
6. Python 3.12→3.13 with the coordinated ML bump.
