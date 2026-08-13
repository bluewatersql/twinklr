# Twinklr Reactivation Proposal (v3)

_2026-08-13. The review's integrating deliverable. v3 = v2's knowledge-loop core
(unchanged) + the lens-audit rework: commercial-lens judgments purged, gap-closure
designs added (stems, MIR modernization, vision-judged evaluation, local provider,
assets revival), human-in-the-loop workflow re-ranked, and the judge-iteration
default flipped. New research citations (all accessed 2026-08-13) are inline; the
adversarially verified code evidence remains `reviews/phases/*.md` /
`verification.md`._

---

## Executive summary

**Twinklr's goal is a system that *learns* what good light-show choreography looks
like, plans shows with what it has learned, and renders them precisely — moving
heads first (mature but wired wrong), full display choreography second (built but
never connected).** The review verified that nearly every needed component already
exists; the defects are wiring, not architecture: a renderer that discards the
planner's intensity and misaligns three time grids, a learning loop with four broken
edges (corpus identity, the apply path, the label loop, the deleted eval writer),
and an LLM layer whose creative output — including the genuinely irreplaceable
lyric-moment interpretation — never reaches the light.

**The plan is two convergent tracks.** Track P repairs the moving-head path behind a
golden-render harness and ships useful output immediately (`.xtiming` timing tracks,
then fresh minimal `.xsq` import, then live `addEffect` injection into a running
xLights — the best-fit workflow for a hobbyist iterating on their own show). Track K
closes the learning loop's four edges and grows a curated, git-tracked choreography
catalog from two supply arms: mining real sequences (propensity: what belongs on a
megatree vs arches vs icicles; taxonomy: choreographic function; stacks: layered
idioms) and LLM-generated candidates, both through the existing human-curation gate.
The tracks converge where display ships as *learned grammar applied to the user's
actual layout*.

**Three modernizations change the approach itself, not just versions:** (1) replace
the hand-rolled beat/downbeat/structure analysis with current MIR models
(`beat-this`, All-In-One) — better ground truth that also kills the three-grid
defect at its source; (2) add demucs stem separation — per-stem onsets/energy are
the highest-leverage new planner signal and fix the weakest analysis link; (3) close
the evaluation loop with **rendered-video judging**: xLights' implemented
`exportVideoPreview` automation + frame-sampled multimodal scoring at ~$0.15/song,
with musical sync measured deterministically (we know the beat grid) and the vision
judge scoring only what code cannot — readability, coordination, variety. Nobody has
done VLM-judged light shows; the adjacent literature supplies the rubric shape and
the warning that shaped this design.

**Sequencing:** M0 makes the repo honest (gates green from a clean checkout — one
fix is literally renaming a loop variable). M1/M1-K run in parallel (render repair +
loop edges). M2 wires the widened plan schema, stems, MIR upgrade, and the
vision-eval harness, then runs the deterministic-vs-LLM comparison as a *validation
gate inside a committed direction* — quality-first defaults, `gpt-5.6-sol` planning,
iteration retained with its feedback defects fixed. M3 ships coordinated MH +
display shows from the catalog. Licensing is a non-issue (personal project); cost is
not a constraint (~$1/song-class); the binding resources are correctness of the
render path and the knowledge the system accumulates.

---

**Fixed constraints from the owner:** core targets unchanged — (1) moving-head
auto-sequencing (most mature), (2) show choreography (unfinished part 2). The
research phase exists so the system can **learn choreography patterns** (not
replicate vendor sequences). Licensing: non-issue; only courtesy rule is
"don't redistribute vendor-derived content." Quality over cost (`gpt-5.6-sol`
planning default).

## 0. Corrections carried into v3

- **0.1** xLights 2026's AI services obsolete nothing (no external hooks); its
  automation API and `.xtiming` import are the usable surfaces. *(v1)*
- **0.2** Display is part 2 of this product. *(v1)*
- **0.3** The corpus pipeline is the learning system; repair its four edges, never
  amputate. *(v2)*
- **0.4** Licensing de-escalated to a footnote. *(v2)*
- **0.5 (v3)** Four skewed lenses identified and purged from the judgment layer:
  commercial-product framing on a personal project (license "gates", "no user
  evidence" strikes, staffing-based rankings); cost-minimization (cut-first defaults
  on judges/iteration); "unreachable = low value" (display, corpus, active-learning,
  assets); and repair-only thinking that named capability gaps without designing
  closures. Corrections: `product-and-approach.md` header note; `findings.md`
  disposition notes; this document's D4/D8 revisions and new D10–D13.

## 1. What the project is trying to accomplish

*(Unchanged from v2 — the knowledge loop.)* The hard problem is **choreographic
knowledge**: a megatree carries spirals/wipes at the chorus, arches chase in
call-response, icicles drip as texture, and the roles coordinate in service of the
music. Hand-encoding cannot cover element-type × moment × style; the system must
learn it:

```
ACQUIRE (sequences aligned to music) → LEARN (taxonomy · propensity · stacks ·
transitions · color arcs · style) → CURATE (recipe synthesis → staged human review;
LLM-generated candidates enter the same gate) → CATALOG (git-tracked, D9)
→ PLAN with learned context conditioned on the USER'S layout → RENDER precisely
→ EVALUATE (deterministic sync metrics + vision-judged quality, D11) → LEARN more
```

The machinery exists end-to-end in code (propensity effect↔element-type affinity,
phrase taxonomy, template/stack mining with support gates, `model_affinities`
conditioning, the group planner's context shaping). Four edges are broken —
identity, apply, labels, evaluation (§2.2) — and the render path beneath it has the
verified defect cluster. Close the edges; make the renderer true.

## 2. Target architecture

### 2.1 Systems and state

| System | Role | State (verified) → v3 change |
|---|---|---|
| Analysis | musical structure substrate | DSP core sound but self-rolled where models now win → **D10 MIR upgrade + D8 stems** |
| Knowledge | corpus → grammar → catalog | machinery complete, 4 broken edges → Track K repairs |
| Performance | plan → render → deliver | MH defect cluster; display unreachable → Track P + M3, plus **D11 evaluation** and **D13 assets** |

### 2.2 The four broken edges *(unchanged from v2)*

1. **Identity**: uuid4-per-ingest defeats corpus accumulation; content hashes
   computed and discarded → content-hash identity.
2. **Apply**: learned context reaches only the CLI-unreachable display planner;
   catalog gitignored → CLI wiring (M3) + catalog-in-repo (D9).
3. **Labels**: learned taxonomy trained on its own rule engine (circular) → wire the
   built-but-orphaned active-learning correction loop.
4. **Evaluation**: writer deleted (restorable, schema drift noted), no result ever
   recorded → restore + **upgrade to the D11 vision-judged loop**.

### 2.3 Performance side *(v2 core + v3 additions)*

MH render-repair campaign behind a golden harness (existing 587-LOC validator);
widened plan schema v2 (typed intensity/color/shutter/gobo intents + lyric
MomentCues, renderer-resolved); macro plan as structured contract; display
composition repairs; unified export core. **v3 additions:** the analysis substrate
upgrade (D10) feeds every grid consumer from ONE model-derived beat/downbeat/section
truth — closing CF-2's three-grid defect at the source rather than patching three
conversions — and the delivery ladder's injection tier is promoted (D2 revision).

## 3. Decision points

**D1 — LLM's role in section planning** *(unchanged)*: widen the channel, with the
deterministic selector built as baseline/fallback/regression arm; standing default
if blind evaluation shows parity.

**D2 — Delivery contract** *(revised ranking)*: fresh minimal `.xsq`+`.xmap` remains
the file contract, `.xtiming` ships first — but **live injection
(`getModels`→plan→`addEffect`) is promoted from "premium later" to a core M2/M3
workflow**. v1 demoted it on a staffing argument (commercial lens); for a hobbyist
iterating on their own show, regenerate-this-section against a running xLights is
the best-fit interaction, and the same session provides D11's render surface.

**D3 — Macro planner** *(unchanged)*: repair to a structured contract; it is the
cross-element coordination spine ("arches answer the megatree" is a macro
statement).

**D4 — Judge/iteration** *(flipped in v3)*: v1/v2's single-pass default was
cost-lens residue. **New default: fix the feedback defects (judge memory, blind
ONESHOT repair) and KEEP iterative refinement**; the D11 harness argues iteration
*down* if it proves valueless — the burden of proof now sits on removal, matching
the quality-first axis.

**D5 — Knowledge supply** *(unchanged from v2)*: mining + LLM generation as
complementary arms into one curated catalog; seeds from hand-authoring; evaluation
feedback as the fourth arm once D11 lands. Nothing extracted; `style_transfer` and
embedding upgrades parked with explicit triggers.

**D6 — Models** *(unchanged)*: sol planning / terra judge / gpt-image-2; explicit
`reasoning.effort`; structured-outputs migration; Dec 2026 retirement deadlines;
include the out-of-framework call site.

**D7 — Python/ML chain** *(updated by research)*: coordinated bump post-M1 — torch
2.8.x, whisperx 3.8.6, pyannote 4.x (delete orphaned diarization first), Python
3.13 ⚖. Watch item: torchaudio is in maintenance wind-down (decode/encode moved to
TorchCodec in 2.10, 2026-01) — prefer deps that don't hard-require it (demucs 4.1.0
already dropped it; beat-this still declares it).

**D8 — Stems (designed, was a mention)**: adopt **demucs 4.1.0** from the
maintained repo (adefossez/demucs — facebookresearch is archived; 4.1.0 released
2026-07-11, MIT, `>=3.10`, torch unpinned so 2.8-compatible, torchaudio no longer
required; MPS automatic on Apple Silicon; htdemucs 9.0 dB SDR, `htdemucs_ft` +0.2
dB at 4× cost). **Integration**: an opt-in, cached analysis stage (≈1–2 min/song
MPS, ~6 min CPU) producing per-stem features — drum-stem onsets → accent/beat
confidence for both planners, bass-stem energy → build/drop truth, vocal-stem
presence → replaces the misaligned full-mix vocal detector as the lyrics/WhisperX
gate. Fallback option if torch-free is ever wanted on macOS: `demucs-mlx`
(single-maintainer risk, noted). Cache key = audio hash + model name.

**D10 (new) — MIR modernization: replace self-rolled beat/structure with current
models.** The original review never seriously evaluated this (repair-lens). Research
verdict:
- **Beats+downbeats: adopt `beat-this`** (CPJKU; PyPI 1.1.0 2026-04-14, MIT code+
  weights, deps just `torch>=2`+torchaudio+einops, ~78 MB, no madmom; GTZAN beat F1
  89.1 / downbeat F1 78.3). Decisive context: **librosa has no downbeat tracker at
  all** — Twinklr's custom phase-voting competes against nothing maintained
  (madmom: no release since 2018, git-install only). Known trade-off: slightly
  lower continuity metrics (CMLt/AMLt) than DBN post-processing; the optional
  `--dbn` flag reintroduces madmom — skip it.
- **Structure labels (verse/chorus): All-In-One** — beats+downbeats+tempo+labeled
  segments in one pass. Canonical `allin1` is install-broken on modern stacks
  (madmom + NATTEN torch-ceiling); on Apple Silicon use **`all-in-one-mlx`**
  (PyPI 1.0.6, 2026-08-12, MIT, no torch/madmom/NATTEN, claims 12.6× on M4;
  single-maintainer risk) or the `all-in-one-fix` fork from git (torch ≤2.7 —
  conflicts with our pin; UNVERIFIED PyPI presence).
- **Keep custom**: energy/multiscale, builds/drops (post-fix), tension, timeline —
  no model equivalent exists and the verified DSP is sound.
- **Adoption gate (honest)**: A/B on golden fixtures against the current BeatGrid
  before switchover — the repo's own test gap (no tempo/beat ground-truth
  assertions anywhere) gets fixed by this A/B's fixture set. Python 3.13 support
  for beat-this is UNVERIFIED (no upper bound declared, no CI claim).
- **Payoff beyond accuracy**: one model-derived rhythmic/structural truth feeds
  planner numbering, renderer placement, and timing tracks — dissolving CF-2's
  three-grid class instead of reconciling it.

**D11 (new) — Vision-judged evaluation loop (closes the loop at scale).**
- **Render**: xLights' `exportVideoPreview` is an implemented xlDo command
  (verified in source; upstream ships `BatchVideoExport.lua` doing exactly
  `openSequence→renderAll→exportVideoPreview→closeSequence`). Frame-stepped (faster
  than realtime), audio muxed in, fps = sequence frame rate. Constraint: needs a
  **windowed** xLights (`--headless` renders fseq only, no video) — fine on the
  owner's Mac; Linux CI unproven.
- **Judge**: OpenAI has no native video input (feature request closed as
  not-planned) → ffmpeg frame sampling at 2–4 fps or 9–16-frame labeled contact
  sheets; 1,500-image/512 MB request limits make a full song fit in one call.
  Cost: ≈$0.13/song at 720p·2fps on gpt-5-mini; ≈$0.66 on terra-class. Gemini is
  the one native-video+audio option but samples at 1 FPS — too coarse for
  beat-level judgment.
- **Design principle (from the literature)**: VLM judges are weakest exactly at
  high-FPS audio-visual sync (Omni-Judge finding; AV-SyncBench separates temporal
  from semantic for the same reason). **So: musical sync is measured
  deterministically** — Twinklr knows the beat grid and every effect's timestamps —
  **and the VLM judges only what code can't**: does the show read well, are models
  coordinated, palette coherent, sections distinct, variety vs monotony. Frames are
  sent WITH Twinklr's own timestamped structure as text, so the judge verifies
  claims rather than guessing.
- **Rubric**: adapt AutoMV's 4-category × 12-criterion pattern to lighting
  (musicality-by-proxy, coordination, color/palette, variety & pacing). Human
  spot-checks stay (all sources: model judges lag experts). **No prior art exists
  for VLM-judged light shows — this is novel and cheap enough to iterate freely.**
- This upgrades M2's comparison from N≥10-songs-with-mandatory-human-ranking to
  **every-run scoring at ~$0.15**, humans sampling instead of gating.

**D12 (new) — Local model provider (offline December).** Feasible with one caveat:
the OpenAI SDK officially supports `base_url` override (constructor or
`OPENAI_BASE_URL`), and Ollama (very active) exposes an OpenAI-compatible surface —
but its `/v1/responses` does **not** document JSON-schema structured outputs;
schema-constrained decoding is supported via `/v1/chat/completions`
`response_format` (and native `/api/chat format`). **Recommendation**: after M2's
structured-outputs migration, add a provider config with a chat-completions
structured-output fallback path; targets for 32 GB machines: `qwen3.5:27b`,
`granite4.1:30b`, or `nemotron-3.5-lightning` (30B MoE) — benchmark against OUR
schemas before trusting any ranking (public rankings are unverified). Priority:
after the cloud path is proven; it's an option, not a dependency.

**D13 (new, was quarantined) — Assets/image generation is a part-2 capability.**
xLights adding first-party AI image generation is *evidence the need is real*
(Pictures effects want imagery). Revive `agents/assets` in M3 with its verified
defects fixed (non-atomic error-swallowing catalog, cross-song reuse-key
collisions, gather-without-return_exceptions), on `gpt-image-2` (deadline: image-1.5
retires 2026-12-01), inside the provider framework. The "spend hazard" framing is
withdrawn; normal cost controls (per-run cap + cache) suffice.

**D9 — Catalog in git** *(unchanged)*: the curated catalog is project knowledge;
raw vendor archives stay local.

## 4. The program (v3)

**M0 — Honest foundation** *(days)*: gates green from clean checkout (RM-0.1..0.4),
packaging fix, onboarding truth. Unchanged.

**M1 [Track P] — Part 1 true**: golden harness → render-repair campaign → channel
defaults → audio truth campaign (now including the vocal-detector fix via D8's
vocal stem where available) → instrumentation + cache identity → eval writer
restored → delivery v1 (`.xtiming` + fresh `.xsq`/`.xmap`, template-merge retired
⚖) → xLights acceptance test.
*Exit*: correct, importable MH show; first recorded evaluation; CLI takes the
user's fixture config.

**M1-K [Track K, parallel]** *(unchanged)*: content-hash identity; active-learning
loop wired; recipe-generation calls into the provider framework; seed catalog
committed (D9).

**M2 [Track P] — Creative quality, measured** *(expanded)*: plan schema v2 +
template channel parameters + data-first loader; lyric MomentCues wired; macro
structured contract; judge feedback repair (D4 — iteration retained); **D10 MIR A/B
then adoption; D8 stems stage; D11 vision-eval harness built** (render client +
frame sampler + rubric judge + deterministic sync metrics); model retarget +
structured outputs (D6); **live-injection workflow v1 (D2)**. Then the three-arm
comparison (deterministic / full LLM / macro-ablated) scored by D11 every run,
humans sampling.
*Exit*: an evidence-backed answer on the LLM's contribution, from a harness that
scores every future change at ~$0.15/song.

**M2-K [Track K]** *(unchanged)*: mining + curation sessions grow the catalog to
the coverage exit (every element type × BASE/RHYTHM/ACCENT × energy range).

**M3 [convergence] — Part 2 ships**: display composition repairs; display pipeline
CLI-reachable consuming catalog + macro arc + user layout; MH+display coordinated;
unified export core; **assets revival (D13)**; injection workflow across both
parts.
*Exit*: one command → coordinated, learned, evaluated show for the user's layout;
evaluation feedback begins flowing into the loop (D5's fourth arm).

**M4 — Compounding**: D7 ML/Python bump; MH-idiom mining exploration; style
transfer at its trigger; D12 local provider; debt retirement; documentation truth
pass.

## 5. Risks and honesty checks

- **New-dependency risk (D10/D8)**: `all-in-one-mlx` and `demucs-mlx` are
  single-maintainer; mitigations — canonical demucs is multi-year stable, beat-this
  is CPJKU-institutional, and the A/B gate means we never depend on a model we
  haven't verified against our own fixtures. beat-this on Python 3.13: UNVERIFIED.
- **D11 render constraint**: video export needs a windowed xLights — fine locally,
  unproven in Linux CI; the harness's CI tier can stop at deterministic
  fseq-compare (`--fseqcmp`) with video judging run locally/scheduled.
- **VLM judge validity**: novel territory; calibrate against human spot-checks
  before trusting trends; never let it judge sync (deterministic metrics own that).
- **Corpus availability** paces Track K (unchanged); LLM-generation arm keeps the
  catalog moving.
- **Weak-supervision circularity** heals only as corrections accumulate (unchanged
  metric: label changes per mining run).
- **Single maintainer**: tracks independently pausable; every milestone exits
  usable.
- **What would change the plan**: D11 scores + spot-checks showing deterministic
  parity (D1 default flips — absorbed); beat-this A/B losing to the current
  BeatGrid on our fixtures (keep DSP, revisit later — absorbed); an external
  choreography hook appearing in xLights (re-rank D2; verify, never assume).

## 6. Non-goals

No rewrite; no UI product; no commercialization scaffolding; no deletion of the
learning system; no display shortcut that skips M1; no MIR/model adoption without
the fixture A/B; no VLM-judged *sync* (deterministic forever).
