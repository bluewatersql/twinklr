# Twinklr Reactivation Proposal

_2026-08-13. This is the review's integrating deliverable: one analysis, one proposed
plan. It supersedes the framing of `final-assessment.md` and `remediation-roadmap.md`
(both retained as appendices; the roadmap's item-level evidence and sequencing traps
remain valid and are referenced by ID). Every claim traces to the adversarially
verified evidence in `reviews/phases/*.md` / `verification.md` / `modernization.md`._

**Fixed constraints from the owner:** the core functional targets do not change —
(1) auto-sequencing moving heads is the most mature capability and part 1 of the
product; (2) choreographing full shows (display) is part 2, largely unfinished, to be
completed rather than deferred. Quality is the optimization axis (per the owner's
retarget of the default model to `gpt-5.6-sol`), not token cost.

---

## 0. Corrections to earlier review claims

Three conclusions from the review's own Stage 2/synthesis were jumps beyond the
evidence. They are retracted or revised here so the proposal doesn't inherit them:

**0.1 — The "commodity squeeze" claim is retracted.** The review argued xLights'
2026 AI features commoditize Twinklr's agent framework and lyrics/audio chain. The
review's own Stage 6 research contradicts that: xLights' AI Services layer is
**configuration-extensible only and scoped to palettes, images, and import-mapping**
— there is no choreography hook, no plugin ABI, and no way for an external tool to
consume xLights' AI or stem-separation capabilities. A capability with no external
hook changes nothing for Twinklr. What survives from that research: (a) the **HTTP
automation API** (`addEffect`, `importXLightsSequence`, `getModels`) is a real,
usable integration surface; (b) stem separation is a capability Twinklr *lacks* and
should **add** (D8), not a reason to concede anything.

**0.2 — "DEFER display" is replaced by "complete display as part 2."** The deferral
verdict treated display as a second product. Under the fixed targets it is the
unfinished half of *this* product. The evidence supports completion: the code is
competent (verified), its defects are enumerated and bounded (P5-F1/F2/F3/F12/M1/M2
— all with corrected mechanisms and known fixes), and its real blocker is **data**
(an empty, gitignored recipe store), not architecture.

**0.3 — "Extract the corpus stack wholesale" is revised to a split verdict.** If
display ships, its runtime supply chain (template store, recipes, theming,
recipe_builder's staged authoring flow) is product infrastructure and stays. What
still leaves the hot tree is the *research* mining pipeline (FE mining, embeddings,
active learning, profiling) — parked until recipe supply actually demands mining,
and gated on vendor-rights resolution (RM-G2) regardless.

---

## 1. The product (position taken)

**Twinklr is an offline-first tool that turns a song into a complete, editable light
show — moving-head choreography first, coordinated display choreography second —
delivered into the user's existing xLights workflow without ever touching their
master sequence file.**

- **User:** an xLights hobbyist with DMX moving heads (a small rig, like the
  author's 4-head setup, is the design center) who can edit sequences but doesn't
  want to hand-author pan/tilt/dimmer curves for every song.
- **Deliverables ladder** (each independently useful, in shipping order):
  1. **`.xtiming` timing/section/lyric tracks** — mapping-free import, already
     backed by the best-tested code in `formats/` (ST-8). Ships almost immediately;
     puts Twinklr output inside real workflows while the rest matures.
  2. **A fresh, minimal `.xsq`** containing only Twinklr's models/effects plus a
     shipped `.xmap` mapping hint — imported into the user's master sequence via
     xLights' import (manually or via `importXLightsSequence`, `mapmethod:"both"`).
  3. **Direct injection** via the automation API (`getModels` → plan against the
     user's real layout → `addEffect`) — the iteration-loop experience (regenerate a
     section while xLights is open), added once 1–2 are true.
- **The user's master file is never an input.** This eliminates the confirmed
  template-content-loss defect (CF-5) by construction and removes the parser from
  the export trust path (it remains for corpus reading only).
- **Quality over cost:** planner-grade calls run `gpt-5.6-sol`; at the verified
  pricing this is roughly $0.59–$1.35/song — acceptable for the value of a good
  show, and cheap relative to the hours saved *if* the output is good, which is what
  Part M2 makes measurable.
- **Commitments the current system doesn't keep, made explicit:** reproducibility
  (same song + config + seed → same show), honesty (degradation is a surfaced
  status, never a silently swallowed exception), and editability (output opens
  clean in current xLights — verified by an in-CI acceptance test, not assumed).
- **Gate:** a LICENSE decision (RM-G1). Until one exists, nobody else may legally
  use this. This is the cheapest highest-leverage item in the entire program.

## 2. Target architecture

One pipeline, two rendering back-ends, one delivery layer. Components marked ✔ exist
and are kept largely as-is; ✚ exist but get repaired/extended; ✖ are cut.

```
audio ──► ANALYSIS ✚          deterministic DSP core (kept) + stem separation (new, D8)
              │                enhancement chain repaired (SF-1/2/3); degradation surfaced
              ▼
        INTERPRETATION ✚      • deterministic features go straight to planners (no LLM re-typing)
              │                • ONE profiling call (sol): creative brief only — mood arc, style,
              │                  section roles (the parts DSP cannot produce)
              │                • lyrics agent (sol): word/phrase MomentCues — THE unique LLM value,
              │                  currently discarded; becomes a first-class plan input
              ▼
        SHOW PLAN ✚           macro arc as STRUCTURED data (D3): per-section energy target,
              │                palette/theme role, motif continuity, cross-section coordination —
              │                consumed by BOTH back-ends as typed fields, never as prompt prose
              ▼
   ┌── MH SECTION PLANNER ✚   widened plan schema v2 (D1): template + preset + intensity +
   │                           color/gobo/shutter intents + lyric-moment events + segmentation;
   │                           deterministic selector as baseline/fallback/regression arm
   │
   └── DISPLAY GROUP PLANNER ✔ (already the best LLM integration in the repo: FE context,
                               auto-repair passes, categorical vocabulary — becomes the model
                               for the MH side rather than the exception)
              ▼
        RENDERERS ✚           MH compile pipeline repaired (CF-1/2/6/7) and extended to resolve
              │                the widened schema; display composition repaired (P5 cluster);
              │                fixture channel DEFAULTS emitted, never zero-fill;
              │                ONE time-grid (real beat grid) shared by planner numbering,
              │                effect placement, and timing tracks
              ▼
        DELIVERY ✚            fresh minimal .xsq + .xmap + .xtiming; automation-API injection
                               optional; display writer's dedup registries harvested as the
                               single export core (ST-5); golden-file + xLights acceptance in CI
```

**The load-bearing design change — widening the LLM→renderer channel (D1/D2 below):**
today the renderer reads two strings per section and the vocabulary never reaches it
(verified). Target: `PlanSection` v2 carries typed intents — categorical intensity
(one enum, actually wired), color intent (palette role or explicit lyric-cue color),
shutter/gobo events (from MomentCues: "sharp white flash on 'ROCK'"), optional
segmentation — and the **renderer alone** resolves them to curves/DMX (the accepted
decision, finally implemented as written). Template layer: parameterized channel
support (~300 LOC mirroring the Dimmer family — the export layer already needs zero
changes, verified P5-V1), plus a **data-first template loader** so the 37 built-ins
migrate progressively from Python to data without a big-bang rewrite.

**Cut (✖), per verified evidence:** the 20 dead solicited schema fields; the
prose-only macro→prompt path (replaced by D3's structured contract); default
multi-iteration judging (D4); one of the two OpenAI clients; the duplicate
emitters/loggers/configs; the confirmed-dead tail (~4–6k LOC, with the recorded
sequencing constraints); the research-mining half of the corpus stack from the hot
tree (D5).

## 3. Decision points — alternatives and recommendations

**D1 — Role of the LLM in moving-head planning.**
- *(a) Deterministic-only:* selector over the verified-discriminating template
  annotations. Free, instant, reproducible, exhaustively testable — and structurally
  incapable of lyric awareness or novel section interpretation; global variety needs
  hand-tuned rules.
- *(b) Widen the channel* (schema v2 above): preserves the product's creative
  thesis; the lyrics agent finally has a sink; cost is trivial at these volumes.
  Risk: more LLM surface to validate; template layer work.
- *(c) Status quo:* pays full LLM cost for two strings of influence. Indefensible on
  the evidence.
- **Recommendation: (b), with (a) built anyway** — as the fallback mode, the
  regression baseline, and one arm of the M2 validation gate. Default standing
  decision: if blind human evaluation cannot distinguish (b) from (a) after the
  channel is genuinely wired, the LLM becomes opt-in per song and the default flips
  to (a). The experiment validates a committed direction; it is not an open fork.

**D2 — Delivery contract.**
- *(a) Keep template-merge and fix fidelity:* requires a preserving parser tracking
  a third-party format forever; the loss class worsens with every xLights release.
- *(b) Fresh minimal `.xsq` + `.xmap` import:* loss-free by construction; mapping
  friction mitigated by the map file and xLights' auto/AI mapping; ~1–2 days of code
  (verified — the parser attaches at one optional site).
- *(c) Automation-API injection:* zero mapping friction, live iteration; requires
  xLights running with the API enabled; unauthenticated local port (document it).
- *(d) `.xtiming` only:* trivial and mapping-free but not a show.
- **Recommendation: (b) as the primary contract, (d) shipped immediately alongside,
  (c) added in M3 as the premium workflow. Retire template-merge.** ⚖ (removes a
  required CLI input — user-facing change).

**D3 — The macro planner.**
- *(a) Cut it:* saves 2–6 calls/song; but the show-level arc (energy narrative,
  palette continuity, motif reuse) is exactly what section-local planning cannot
  see, and part 2 (display) needs cross-section coordination even more than MH does.
- *(b) Keep as-is:* its output provably never reaches rendering except as prose —
  the current state is the worst of both.
- *(c) Repair to a structured contract:* MacroPlan slims to the fields both
  back-ends actually consume (typed, versioned, in the plan-section inputs), judge
  kept single-pass.
- **Recommendation: (c).** The macro layer becomes the show-coherence spine of the
  two-part product — the thing that makes MH and display *one* choreography. This
  reverses the review's earlier "cut" lean, on the owner's product definition plus
  the display-side evidence (its group planner already consumes structured context
  well).

**D4 — Judge/iteration loop.**
- *(a) Remove judging:* cheapest; loses the only quality backstop until the eval
  harness matures.
- *(b) Keep 3-iteration loops:* no evidence of value in the repo's entire history;
  known defects (judge has no memory; ONESHOT repair is a blind resample).
- *(c) Single judge pass, hard-fail-only revision, with the feedback defects fixed*
  (judge sees prior verdict + plan diff; repair shows the model its failing output).
- **Recommendation: (c)**, and let the M2 harness — not intuition — argue iteration
  counts back up if the data supports them.

**D5 — Corpus/FE stack.**
- *(a) Extract everything:* clean tree, but amputates display's supply chain.
- *(b) Keep everything hot:* ~24k LOC taxing every gate run, mostly research.
- *(c) Split:* **runtime supply chain stays** (template store, EffectRecipe,
  theming, recipe_builder staged authoring — the path that turns a curated catalog
  into display shows); **research mining parks** (FE mining, embeddings, active
  learning, profiling) — extracted or archived until display's recipe demand
  justifies mining, and never resumed before the vendor-rights gate (RM-G2). Fix
  the uuid→content-hash identity defect (P6-M2) whenever it wakes.
- **Recommendation: (c).** Display's M3 catalog is bootstrapped by *authoring*
  (hand-seeded + recipe_builder curation), not mining — mining is an optimization
  with a legal gate, not a dependency.

**D6 — Models and API surface.**
- **Recommendation (owner-aligned):** planners + profile + lyrics on `gpt-5.6-sol`
  (quality axis, per the owner's edit); judge on `gpt-5.6-terra`; image work (if/
  when assets revive) `gpt-image-2`. Explicit `reasoning.effort` per role (5.6
  defaults to medium — a silent cost/latency change otherwise). Migrate to strict
  structured outputs (`responses.parse` + Pydantic) after the one-call probe;
  hard deadlines stand (image model 2026-12-01, current judge model 2026-12-11).
  Include the out-of-framework call site (`normalization/llm_review.py`) in the
  retarget sweep. Cache note: model IDs are already in cache keys (retarget-safe);
  prompt-content hashing must land with the session-ID fix.

**D7 — Python/ML chain.**
- **Recommendation:** coordinated single change after M1 stabilizes — torch/
  torchaudio 2.8.x + whisperx 3.8.6 + pyannote 4.x (delete the orphaned diarization
  module first; it's where the major-version breakage concentrates) + Python
  3.12→3.13 ⚖. Not before: it's churn with no user-visible payoff until the core is
  true.

**D8 — Stem separation (new capability).**
- *(a) Skip it:* full-mix analysis only, as today.
- *(b) Add HTDemucs-based stems* (drums/vocals/other) feeding rhythm and vocal
  features: better beat/onset evidence for MH accents, better vocal-presence truth
  for lyrics gating (fixes the current detector's role after its alignment bug is
  repaired), and it feeds MomentCue placement.
- **Recommendation: (b), in M2** — it strengthens exactly the features both
  planners consume. (Not because xLights has stems — because our own evidence shows
  full-mix vocal detection is the weakest analysis link.)

## 4. The delta, evidence-mapped

Every workstream exists because the target needs it — not as free-floating repair:

| Target property | Today (verified) | Workstream |
|---|---|---|
| Output represents planned intent | Intensity always SMOOTH; BLACKOUT renders bright; floors dropped; calibration annihilated; short sections empty (CF-1/6) | W2 render-repair campaign |
| One musical time base | Three misaligned grids incl. planner-side floor (CF-2) | W2 (spans agents+sequencer) |
| Light actually comes out per fixture defaults | Zero-fill vs declared `shutter_default=255` (CF-7) | W2 channel-default policy |
| LLM value reaches the show | Two-string channel; lyric agent blind-wired; macro = prose (CF-3/4) | W4 schema v2 + D3 contract |
| System can measure itself | Eval writer deleted; token attribution races; knobs inert (SF-4, CC-4, CC-1) | W3 instrumentation + eval restore |
| User's files are safe | Unconditional template-content loss (CF-5) | W5 delivery contract |
| A second person can run it | No LICENSE; broken onboarding; gates fail from clean checkout (SF-7, CC-2) | W1 + RM-G1 |
| Part 2 exists | Display unreachable; composition defects; empty recipe store (0.2, SF-6) | W6 display completion |
| Honest degradation | CC-3 silent-failure class | W3 observability spine |
| Current platform | Model retirements Dec 2026; torch 2.4-era chain | W7 modernization |

## 5. The program

Workstreams (W) ordered by dependency; milestones (M) are shippable states. Effort
is calibrated to a single maintainer with agent assistance; each milestone ends with
its exit criteria, and the item-level details live in the roadmap appendix by RM-id.

**M0 — Honest foundation** *(days)*
W1: gates green from clean checkout (RM-0.1..0.4: the one-variable mypy fix,
structural test repair, format/lint baseline, minimal check-only CI), packaging via
`uv_build` (RM-0.5), onboarding truth (RM-0.6), **LICENSE decision (RM-G1)** ⚖.
*Exit:* CI green on a fresh clone; a second person may legally clone and run it.

**M1 — Part 1 true: the moving-head auto-sequencer works as designed** *(the core
investment)*
W2: golden render harness FIRST (wire the existing 587-LOC validator, pin golden
settings-strings, shutter-channel test, one round-trip test — RM-1.0), then the
render-repair campaign as one golden-diffed branch (RM-1.1: intensity+data-fill+
frequency-amplitude together; floors; BLACKOUT; calibration; scheduler; single
time-grid including the planner-side fix), channel defaults (RM-1.2).
W3: instrumentation + truth (RM-1.3 audio campaign incl. metadata clients + MB
limiter together; RM-1.4 token attribution, cache identity + prompt hashing, config
triage start; RM-1.6 eval writer restored + `eval-report` bridged).
W5: delivery contract v1 — `.xtiming` output + fresh minimal `.xsq`+`.xmap`; retire
template-merge ⚖; empirical xLights acceptance test in CI (import into 2026.15,
current stamp).
*Exit:* a song renders to a correct, importable show; **the first committed
evaluation result + recorded human judgment in the project's history**; CLI takes a
fixture config instead of hardcoding the author's rig.

**M2 — Creative quality, measured** *(where the LLM earns its keep)*
W4: plan schema v2 + template channel parameters + data-first loader (progressive
re-authoring of the 37 templates); lyric MomentCues wired end-to-end; macro
structured contract (D3); judge repair (D4); deterministic selector arm; **the
three-arm blind-eval gate with D1's standing default**; stems (D8).
W7 (parallel, deadline-driven): model retarget per D6 + structured outputs.
*Exit:* an evidence-backed answer to "does the LLM make better shows," and either a
validated creative pipeline or a deliberate deterministic default — both are wins.

**M3 — Part 2: show choreography** *(display completion)*
W6: display composition repairs (P5 cluster: sequencing math, blend-mode
structural loss, TRIM gaps); recipe catalog bootstrap by authoring (seed set +
recipe_builder staged curation — D5); macro-arc coordination across MH + display;
CLI exposure of the display pipeline; harvest/unify the export core (dedup
registries, one emitter — also fixes the stamp/grid divergence).
W5+: automation-API injection workflow (D2c).
*Exit:* one command produces a coordinated MH + display show for a real layout;
corpus mining remains parked behind RM-G2 unless recipe demand reopens it ⚖.

**M4 — Continuous** *(threaded through, not an era)*
W7: ML chain + Python 3.13 (D7, post-M1); debt retirement per the recorded
sequencing constraints (RM-5.x); documentation truth pass — the user guide
regenerated from *wired* config only, the "dozens of hours" claim replaced by
measured numbers from M1/M2.

## 6. Risks, costs, and what would change this plan

- **Biggest technical risk:** template re-authoring scale in M2. Mitigated by the
  data-first loader (progressive migration, not big-bang) and by the fact that the
  export layer verifiably needs zero changes.
- **Biggest empirical unknowns (all cheap to resolve early):** bare-`.xsq` import
  without `rgbeffects.xml` (M1 W5 test); `json_object` acceptance on 5.6 (one call,
  before W7's structured-outputs step); physical shutter mapping (the written
  channel-6/17 test + one real-rig check).
- **Biggest schedule risk:** single-maintainer attention. The plan front-loads
  deletion and measurement precisely because every retained line taxes every later
  step; M1 is deliberately the largest single investment because part 1 being
  *true* is what everything else stands on.
- **Cost:** ~$1/song-class LLM spend at sol-tier planning (measured properly from
  M1's instrumentation, replacing the estimate); pyannote-4.x migration risk is
  bounded by deleting its only (orphaned) consumer first.
- **What would change the plan:** the blind eval failing D1's default (flips the
  creative default to deterministic — the plan absorbs this by design); the owner
  declaring this a hobby rather than a product (drops M0's second-person goals and
  the LICENSE urgency, nothing else); xLights shipping an actual external
  choreography hook (would re-rank D2c upward — to be *verified* against release
  notes, not assumed).

## 7. Non-goals (explicit)

No rewrite. No provider swap. No UI product. No marketplace/distribution ambitions
beyond making a second user legal and able. No corpus mining before the rights gate.
No display revival shortcut that skips M1 — part 2 inherits every part-1 repair
(shared exporter, shared time grid, shared macro contract), which is exactly why the
order is what it is.
