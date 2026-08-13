# Product Thesis & System-Approach Review (Stage 2)

_Authored 2026-08-13 by the Stage 2 architect (opus, non-author of discovery), verified
against source at baseline `aa8d325`; competitive/pricing claims rest on Stage 6
official-source research (access date 2026-08-13). Conclusions are PROVISIONAL until
Stage 3 verifies the five items in §8 and Stage 7 adversarially reviews. The architect
personally verified the three load-bearing findings and corrected two discovery counts
(37 registered templates, not 38 — the 38th is a docstring example; moving-head
planning is SEQUENTIAL, not fanned out — FAN_OUT exists only in the display pipeline)._

## Headline

The shipped product is far smaller than every document claims, and the LLM's
contribution is smaller still. On the only runnable path, the entire multi-agent
apparatus (5–14 LLM calls) resolves to **two strings per song section**: a
`template_id` (37 options) and a `preset_id` (~5 effective) — 193 discrete outcomes.
Everything else the models emit is discarded before rendering (OBSERVED,
`moving_heads/pipeline.py:226-238`: the renderer reads exactly five plan fields).

Three verified findings drive everything:

1. **`MacroPlan` never reaches the shipped renderer** — zero references in
   `sequencer/moving_heads/`; it influences output only as rendered prose inside the
   next agent's prompt (`moving_heads/prompts/planner/user.j2:117-138`). Cost: 2–6
   gpt-5.2 calls per song.
2. **Color, gobo, and shutter are unwired.** 0 of 37 templates reference them;
   `ColorLibrary`/`GoboLibrary`/`ShutterLibrary` have no consumers;
   `JobConfig.is_channel_enabled()` and `ChannelDefaults` are never read. The shipped
   product choreographs **pan, tilt, dimmer only** — `docs/overview.md:24` claims six
   channels.
3. **The interpretation the LLM produces is destroyed before it lands**: the lyrics
   agent produces genuinely irreplaceable word-level cues ("sharp white flash on hard
   'K'…"), but the only sink is a section-level template choice in a system with no
   color channel. The audio-profile agent re-derives values already printed into its
   own prompt, and its "most important" output (`planner_hints`) is never passed to
   the macro planner.

## 1. Target user & job — UNVALIDATED_ASSUMPTION

One contributor across 148 commits; **no LICENSE has ever existed in any commit** (also
absent from every pyproject) — legally nobody else may use it; no runnable example
(no tracked audio/xsq; required configs gitignored). The real rig, visible in deleted
history (`b6fdfd2`): four moving heads, one song, one yard.

The "replaces dozens of hours" claim traces commit-by-commit to a deleted blog draft's
literal "Opening Hook" (2026-02-12), then README (39 minutes later), then docs
(2026-03-08), then canonical context (2026-08-13) — never gaining a source. It must
not be treated as an input to Stage 8. The need is now better supported by the
**absence of a competitor** (§2) than by anything in the repository — a real update,
but still not user evidence.

## 2. Product boundary & round-trip contract

The CLI takes the user's real sequence as input (signalling "merge") then silently
drops everything unmodeled (confirmed defect, discovery §5). Stage 6 intel worsens
this into a **decay argument**: xLights' 2026 format changes are additive, and every
additive field is one more thing `extra="ignore"` silently drops — the defect widens
with every xLights release while Twinklr stands still.

**PROPOSED contract — generate-fresh, narrow-surface, import-mediated**: emit a NEW,
minimal `.xsq` containing only Twinklr's moving-head models and timing tracks; never
accept the user's master sequence as input; the user imports effects via xLights' own
effect-import. Eliminates the data-loss defect by construction, removes the parser
from the trust path, shrinks the least-tested package to a write-only surface.
**Dependency: whether xLights' effect import accepts a minimal external `.xsq` —
Stage 6 follow-up + Stage 4 empirical test.**

**Competitive picture (verified)**: xLights 2026 ships first-party AI Services
(ChatGPT/OpenAI-generic/Ollama), AI image generation, stem-aware AI lyrics with
HTDemucs separation — but **no full-song choreography generation. The thesis is
unoccupied.** The commodity squeeze lands on Twinklr's largest investment: the 21k-LOC
agent/provider framework and parts of the lyrics/audio chain duplicate what the host
now provides (with stems — which Twinklr lacks). **The moat is the template library +
renderer + selector logic (16.7k LOC), not the agent framework.** The architect's
prior assumption that xLights had moving-head choreography effects was wrong and is
retracted on verified evidence.

## 3. Scope coherence — accumulated experiments

Measured: ~26k LOC reachable from the CLI vs **~32k unreachable** (feature_engineering
16.1k, display 8.3k, reporting/evaluation 3.5k, recipe_builder 2.6k, feature_store
1.7k — all NO). Proposed smallest useful reactivation scope:

- **KEEP + REPAIR**: audio analysis, moving_heads + curves renderer, exporter half of
  formats/xlights, CLI.
- **PROMOTE FIRST**: `reporting/evaluation` — the only subsystem that can answer any
  quality question; one CLI entry point from usable. Wire before repairing anything.
- **DEFER**: display pipeline (coherent second product; revival re-opens image spend).
- **ABANDON or SPLIT OUT**: feature_engineering + feature_store + recipe_builder
  (~20k LOC): premise unvalidatable (corpus gitignored), feeds only the unreachable
  pipeline, taxes every refactor.

## 4. Is the LLM load-bearing? — On the shipped path, as built: NO — but the reason matters

**For a deterministic selector**: template selection is close to a table join —
templates carry `energy_range`, `recommended_sections`, `tags`; sections arrive with
label + energy; the prompt writes the join key out in prose; and
**`recommended_sections` — the exact column that makes the join exact — is loaded,
carried, serialized, and never rendered into the prompt** (`user.j2:47` emits only
description/energy_range/tags). Segmentation, the one discretionary decision, is
actively suppressed by the prompt ("default to 1 template per section"). A ~few-hundred
-line selector reproduces most behavior; 193 outcomes are exhaustively testable.

**What the LLM adds**: exactly one agent does irreplaceable work — the lyrics agent
(word-level semantic cues). The architecture throws its output away (no color channel,
section-level sink). The audio-profile agent re-derives values printed into its own
prompt at frontier prices.

**Verdict**: the system pays full LLM cost for near-zero LLM information throughput.
**The bottleneck, not the model, is the problem.** The real choice: (i) widen the
channel (templates exposing color/gobo/shutter, accepting parameters) so
interpretation reaches the renderer, or (ii) drop the LLM for a deterministic
selector. The current design is the expensive half of both.

Agent-by-agent: audio profile → REPLACE with deterministic code; lyrics → KEEP
(currently wasted); macro planner + judge → CUT from the moving-heads path (prose-only
influence); MH planner → deterministic-by-default with LLM as A/B arm; MH judge → CUT
until evidence justifies (no artifact anywhere shows iteration improving output).

**Resolving experiment**: wire eval harness → build deterministic selector → N≥10
songs × 3 arms (deterministic / full LLM / macro-ablated) → score with existing
harness + **blind human ranking of xLights previews** (mandatory — the harness
measures only self-consistency) → record cost/latency/tokens.

## 5. Success criteria — none exist today

Proposed: timing accuracy (ms vs beat grid — already computable); choreography quality
(blind human pairwise ranking); physical validity (already implemented in
`reporting/evaluation/{physics,continuity}.py`); editability (opens in xLights, edit +
re-save without loss); reproducibility (same inputs → byte-identical .xsq — currently
impossible: random session UUID + sampling); latency & USD per song; user effort.

**No evaluation result has ever been committed.** The only quality number that ever
existed — `overall_score: 90.61` in deleted history — was the LLM judge grading the
LLM planner, uncalibrated, no human. Across the entire knowledge tree there is not one
recorded human opinion about a generated show. (Strengthens discovery H4.)

## 6. Cost & operational model (verified pricing)

Per song (INFERRED tokens × OBSERVED pricing): gpt-5.2 ≈ **$0.25 best / $0.58 worst
case** (± reasoning tokens, the largest uncertainty); terra ≈ same; sol ≈ $0.59–1.35;
luna ≈ $0.02–0.06. **Cost is NOT the binding constraint — the two-string-wide channel
is.** This shifts weight toward widening the channel (option c): the blocker was never
economics; it is that 0/37 templates touch color.

Operational: defeated cache = full latency every tuning iteration (small fix, big
product impact); `token_budget: 75000` documented as a live knob, confirmed no-op;
**new bug: `AgentOrchestrationConfig.judge_agent` is never wired — both orchestrators
call `get_judge_spec()` with no model arg, so the macro judge silently runs gpt-5.2,
not gpt-5-mini**; privacy: full lyrics + metadata go to a third-party API, no
user-facing statement; connectivity: needs internet + paid key (xLights now has an
Ollama/local option); licensing: absent, blocks distribution.

## 7. Alternatives — scored post-intel

(a) **Deterministic template+rules** — holds as the instrumented measurement baseline;
free, instant, reproducible, exhaustively testable. (c) **Wider-channel model-driven**
— rises to co-primary now that cost is known trivial; clearest path to a defensible
product; reopens the numeric-hallucination risk the accepted decision guards against.
(e) xLights integration — resolves into the §2 boundary contract, not a separate
strategy. (b) repair-as-is — low (repairs plumbing, not thesis). (d) human-in-the-loop
— best product fit, worst effort fit for one maintainer (needs a UI; makes
nondeterminism a feature). (f) archive — **drops**: the thesis is unoccupied and the
moat is real.

## 8. Recommended direction

**Thesis (PROPOSED)**: Twinklr's defensible core is deterministic audio analysis + the
tested pan/tilt/dimmer renderer. The product: a fast generator of moving-head
sequences emitting a minimal `.xsq` for import into the user's master sequence. The
LLM re-enters only where it demonstrably beats the deterministic baseline on a
measured comparison, and only after the channel can carry its judgment to the renderer.

**Path**: (a) as instrumented baseline explicitly in service of deciding (c). The
question is no longer "can we justify LLM cost" but **"does the LLM add enough to
justify rebuilding the template layer to let it through."** Order deliberately:
**instrument first, then decide, then repair.**

**Top 5 Stage 3 verifications** (phase assignments in parentheses):

1. Color/gobo/shutter unwired across the full render path + how hard adding color
   would be — parameter plumbing or redesign? (phases 4, 5)
2. `MacroPlan` reaches the shipped renderer only as prompt prose — no indirect route.
   (phases 3, 4)
3. Deterministic-selector feasibility: are `energy_range`/`recommended_sections`
   populated and discriminating across all 37 templates? (phase 4)
4. Do generated `.xsq` files open in real xLights (2024.10 stamp vs 2026.15)?
   (phase 5 + Stage 4 empirical)
5. Dead configuration surfaces as a CLASS (token_budget, judge_agent,
   is_channel_enabled, ChannelDefaults, checkpoint, AppConfig.logging) — the user
   guide cannot currently be trusted as a behavior description. (phases 1, 7)

**Would change the verdict**: LLM arm winning blind human evaluation (genuinely
possible — global variety/anti-repetition is a property naive rules handle badly);
sparse/non-discriminating template annotations; the author declaring this a hobby
(reranks (a)/(d), makes (b) reasonable).

**Accepted-decision conflicts flagged for Stage 8 project decisions**:
`memories/decisions/llm-plans-intent-renderer-implements-precision.md` — principle
sound, but its description of reality matches only the unshipped display pipeline (the
shipped LLM emits no categorical intensity/duration enums and no creative arc reaches
the renderer); `context/product/overview.md` three-scope + "dozens of hours" claims;
`docs/overview.md:24` six-channel claim; macro-planner removal would overturn
documented central architecture.

**Stage 6 follow-ups — ANSWERED (see modernization.md M6b, access date 2026-08-13)**:
(1) AI Services is config-extensible only and scoped to palettes/images/mapping — not
an entry point; the real extension surfaces are Lua scripting and the **HTTP
automation API** (`importXLightsSequence`, `addEffect`, `getModels`, no documented
auth). (2) Effect import accepts xLights donor sequences with effects + timing tracks
into the open sequence; mapping is the friction, mitigable by shipping `.xmap` or
API-triggered `mapmethod:auto|both`; a bare-`.xsq`-without-rgbeffects import is the
one UNVERIFIED point (Stage 4 test). (3) Version cutoff is pre-2020 only (warning,
not rejection) — "2024.10" is fine today; ratchet risk noted.

**Contract addendum (post-research)**: the §2 generate-fresh contract is confirmed
viable and gains two variants — a `.xtiming`-only deliverable (mapping-free, trivial;
a candidate MVP for the audio-analysis value alone) and **direct `addEffect` injection
against the user's real models via the automation API**, which eliminates the mapping
problem at the root and inverts the integration from "export and hope" to "drive the
host app." Stage 8 must weigh all three; the direct-injection option also dissolves
most of the `.xsq`-emission surface if chosen.
