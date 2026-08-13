# Twinklr Reactivation Proposal (v2)

_2026-08-13. The review's integrating deliverable: one analysis, one plan. v2 is a
substantive rewrite after the owner corrected v1's misreading of the corpus
subsystem's purpose. Supersedes `final-assessment.md` and `remediation-roadmap.md` as
the plan (both remain evidence appendices; RM-x.y item IDs are still referenced for
item-level detail). Every factual claim traces to the adversarially verified evidence
in `reviews/phases/*.md` / `verification.md` / `modernization.md`._

**Fixed constraints from the owner:**
- Core functional targets do not change: **(1)** auto-sequencing moving heads — the
  most mature capability; **(2)** choreographing full shows — the largely unfinished
  second part.
- **The research/corpus phase exists so the system can LEARN choreography** — what
  megatree choreography looks like, what it means to sequence arches in a yard with
  icicles. Learning patterns is the point; replicating any particular vendor sequence
  is not.
- Licensing is a non-issue: this is a personal, non-commercial project. (One residual
  courtesy rule only: don't *redistribute* vendor-derived content. Learning from
  purchased material for personal use is normal use.)
- Quality over cost: planner-grade calls on `gpt-5.6-sol` (owner's edit).

---

## 0. Corrections carried into v2

**0.1 (from v1) — xLights 2026 obsoletes nothing.** Its AI services have no external
hooks (verified); a capability you cannot consume changes nothing. What matters from
that research: the HTTP automation API (`getModels`, `addEffect`,
`importXLightsSequence`) is a usable integration surface, and `.xtiming` import is a
mapping-free delivery channel.

**0.2 (from v1) — display is part 2 of this product**, not a deferred second product.

**0.3 (v2, replaces v1's §0.3/D5) — the corpus pipeline is the learning system, and
v1 was wrong to cleave it off.** v1 recommended parking the mining pipeline and
bootstrapping display recipes "by authoring" — silently replacing machine learning
with the hand-labor the project exists to eliminate, and leaving no answer to *where
the system learns what a megatree does during a chorus*. The evidence never supported
amputation; it supported **repair of the loop's broken edges** (identity, the apply
edge, the label loop). §2 and D5 are rebuilt around that.

**0.4 (v2) — licensing de-escalated.** v1's RM-G1 "gate" treated a personal project
like a distribution business. Dropped. The only standing note: if distribution is
ever wanted later, add a license then; and don't redistribute vendor-derived content
meanwhile.

---

## 1. What the project is trying to accomplish

**Twinklr turns a song plus a description of *your* display into a complete,
coordinated light show — moving heads and display elements — that looks like it was
choreographed by someone who knows what they're doing.**

The hard problem is not rendering (deterministic code does that) and not musical
analysis (DSP does that). The hard problem is **choreographic knowledge**: knowing
that a megatree carries spirals and wipes at the chorus, that arches chase and
leapfrog in call-response, that icicles drip and twinkle as texture, that these roles
coordinate rather than compete, and that all of it must serve the music's structure.
No hand-written rulebook covers every element type × musical moment × style; humans
encode some of it (the 37 MH templates), but the display side across heterogeneous
layouts is exactly where hand-encoding stops scaling.

**Therefore the system's defining loop is a knowledge loop:**

```
        ACQUIRE                 LEARN                    CURATE
  sequences (vendor packs,   taxonomy: choreographic   recipe synthesis →
  community, own shows)  ──► function of each phrase   staged human review ──► CATALOG
  aligned to music           propensity: what belongs  (recipe_builder;          │
  (profiling + FE align)     on WHICH element type     LLM-generated candidates  │
                             templates/stacks: layered enter the same gate)      │
                             idioms; transitions;                                │
                             color arcs; style                                   │
                                                                                 ▼
        EVALUATE ◄──────────── RENDER ◄──────────── PLAN with learned context
  harness + human judgment   deterministic,          planner sees: catalog filtered
  → feeds propensity/labels  precise (both parts)    by the USER'S layout via
  (active-learning loop)                             propensity/model_affinities,
                                                     style constraints, macro arc
```

Nearly all of this **already exists in the repository** — that is the review's most
important structural fact once read correctly. What's broken is not the idea or most
of the machinery; it's four specific edges (§2.2) plus the part-1 renderer defects.
The proposal is: **close the loop, and make part 1 true while doing it.**

**Where the system learns megatree/arches/icicles choreography — the concrete
answer:** `PropensityMiner` learns effect↔element-type affinity from real shows
(`propensity.py`: co-occurrence over `target_name`→model-type); the taxonomy
classifies each mined phrase's choreographic function (BASE/RHYTHM/ACCENT);
template/stack mining captures multi-layer idioms with support/stability stats;
recipes carry `model_affinities` and `motif_compatibility` so that, at plan time, the
catalog is **conditioned on the user's actual layout** (element types from
`xlights_rgbeffects.xml` via the layout parser / `getModels`), and the group planner
already consumes exactly this context (`context_shaping.py` — verified working glue).
The knowledge path exists end-to-end in code. It has never been connected to a
runnable product path — that is the defect, and it is a wiring defect, not a design
one.

**Delivery (unchanged from v1):** never touch the user's master sequence. Ladder:
`.xtiming` timing/section/lyric tracks (immediate) → fresh minimal `.xsq` + `.xmap`
import → automation-API injection (`getModels` → plan against real layout →
`addEffect`) as the live-iteration workflow. The layout the API/rgbeffects provides
is *also* what conditions the learned catalog — delivery and knowledge share the same
layout contract.

## 2. Target architecture

### 2.1 The three systems and their state

| System | Role | State (verified) |
|---|---|---|
| **Analysis** (audio → musical structure) | shared substrate for everything | DSP core sound; enhancement chain broken in known ways (SF-1/2/3); stems missing (D8) |
| **Knowledge** (corpus → grammar → catalog) | the learning loop above | machinery complete; four broken edges (§2.2); never connected to a shipped path |
| **Performance** (plan → render → deliver) | MH = part 1; display = part 2 | MH renderer defect cluster (CF-1/2/6/7); display code-complete, unreachable, composition defects known (P5) |

### 2.2 The four broken edges of the knowledge loop (all verified, all repairable)

1. **Identity**: re-ingesting the same archive mints new uuid4 primary keys while
   content hashes are computed and discarded (P6-M2) — the corpus cannot accumulate
   idempotently. Fix: content-hash identity (`zip_sha256`/file sha) as the key.
2. **The apply edge**: learned context reaches only the display planner, which no
   product command runs; the recipe catalog lives only in a gitignored local store.
   Fix: display pipeline reachable from the CLI (part 2), catalog treated as a real,
   versioned data artifact of the project (tracked seed catalog + local extensions —
   it is project knowledge, not scratch).
3. **The label loop**: the "learned" taxonomy is trained on the rule engine's own
   output (weak-supervision circularity, P6 verified) — it cannot exceed the rules.
   The fix **already exists as code**: the orphaned `active_learning` stages
   (`UncertaintySampler` → `ReviewBatchBuilder` → oracle/human → `CorrectionApplier`)
   are precisely the human-corrections loop that breaks the circularity. Wire them
   (v1 called this "half-built, orphaned"; correct reading: built, unwired).
4. **Evaluation feedback**: the eval harness's writer was deleted (restorable ~10
   lines, schema-drift trap documented) and no result was ever committed — so
   nothing the system produces ever teaches it anything. Fix: restore writer, bridge
   CLI, and record human judgments alongside harness scores (these judgments are
   also future propensity/quality signal).

### 2.3 Performance side (carried from v1, unchanged in substance)

- **MH render repair campaign** (CF-1/2/6/7 cluster: intensity, single time-grid,
  scheduler, calibration, floors, BLACKOUT inversion, channel defaults instead of
  zero-fill) behind a golden harness built on the existing 587-LOC validator.
- **Widened LLM→renderer channel** (D1): plan schema v2 with typed intents —
  categorical intensity (one enum, actually wired), color/shutter/gobo intents,
  lyric MomentCues (the lyric agent finally gets a sink) — resolved by the renderer
  alone. Template layer: parameterized channels + data-first loader; and note the
  convergence — **a data-first MH template is structurally a recipe**, which over
  time lets MH templates live in the same catalog/curation flow as display recipes
  (one knowledge store, two renderers).
- **Macro plan as structured contract** (D3): the show-coherence spine both parts
  consume as typed fields, never prompt prose.
- **Display composition repairs** (P5 cluster) when part 2 wires up.
- **Export core unified** on the display writer's dedup registries (ST-5), one
  emitter, one stamp/grid policy.

## 3. Decision points — alternatives and recommendations

**D1 — LLM's role in section planning** *(unchanged from v1)*: deterministic-only
(a) vs widened channel (b) vs status quo (c). **Recommend (b) with (a) built as
baseline/fallback/regression arm**; standing default: if blind evaluation can't
distinguish them once the channel is honestly wired, default flips to (a) with LLM
opt-in. The experiment validates a committed direction.

**D2 — Delivery contract** *(unchanged)*: fresh minimal `.xsq`+`.xmap` primary;
`.xtiming` immediate; automation-API injection as the premium loop; retire
template-merge ⚖ (removes a required CLI input).

**D3 — Macro planner** *(unchanged)*: repair to a structured contract (not cut, not
prose). It is the cross-element coordination layer — "arches answer the megatree" is
a macro-level statement.

**D4 — Judge/iteration** *(unchanged)*: single-pass judge with the feedback defects
fixed; iteration counts must earn their way back via the harness.

**D5 — The knowledge system (rewritten).** How should the system come to know
choreography?
- *(a) Hand-encode it* (templates/recipes written by the author): rejected as the
  primary mechanism — it's the labor the project exists to remove, and it cannot
  cover element-type × moment × style diversity. It remains the **seed** mechanism
  (the 37 MH templates prove its value at small scale).
- *(b) LLM-embedded knowledge*: prompt models to propose recipes. Ungrounded in what
  actually reads well on physical elements — but cheap, diverse, and **already
  implemented** as recipe_builder's generation phase feeding the same staged review.
- *(c) Learn from real shows* (mining): grounded, layout-aware (propensity),
  style-aware (fingerprints), statistically gated (support/stability) — **already
  implemented** end-to-end minus the four edges.
- *(d) Learn from own output + evaluation* (closing the outer loop): the long-term
  compounding mechanism; needs edge 4 first.
- **Recommendation: (c) + (b) as complementary supply arms feeding ONE curated
  catalog** — which is literally what `recipe_builder` already is (mined evidence
  enriches LLM candidates; humans admit) — with (a) as seeds and (d) wired as soon
  as evaluation lands. Repair the four edges rather than parking anything. The only
  pieces that stay parked until their trigger: `style_transfer` re-ranking (trigger:
  catalog large enough that retrieval ranking matters) and embeddings beyond
  brute-force (trigger: corpus scale actually hurts). Nothing is extracted from the
  repo. ⚖ reverses v1's D5.

**D6 — Models** *(updated)*: sol for planners/profile/lyrics, terra judge,
gpt-image-2 when assets revive; explicit `reasoning.effort`; structured-outputs
migration after the probe; retirement deadlines stand (Dec 1 / Dec 11, 2026);
include the out-of-framework call site in the sweep. The knowledge loop adds one:
recipe-generation calls (currently raw client) move inside the same provider
framework.

**D7 — Python/ML chain** *(unchanged)*: coordinated bump post-M1 (torch 2.8.x,
whisperx 3.8.6, pyannote 4.x — delete orphaned diarization first), Python 3.13 ⚖.

**D8 — Stems** *(unchanged)*: add HTDemucs-based separation in M2 — our own evidence
shows full-mix vocal detection is the weakest analysis link; drum-stem onsets
sharpen accent placement for both parts.

**D9 (new) — Catalog as project knowledge.** Where does the learned catalog live?
- *(a) Gitignored local store* (today): the loop's output evaporates per-machine;
  partly why the apply edge never closed.
- *(b) Track a curated catalog in-repo* (seed + admitted recipes; mined-statistics
  provenance retained; large raw corpora stay local): makes knowledge durable,
  reviewable, versioned — consistent with the repo's own knowledge-management
  philosophy.
- **Recommendation: (b).** Raw vendor archives stay local (size + courtesy); the
  *learned, curated* artifacts are the project's crown jewels and belong in git.

## 4. The program

Two tracks that converge, instead of v1's strictly serial milestones: **Track P
(performance)** makes part 1 true; **Track K (knowledge)** closes the loop; they
merge in M3 where part 2 ships as *learned grammar, applied*. M0 precedes both.

**M0 — Honest foundation** *(days; unchanged from v1 minus the license gate)*
Gates green from a clean checkout (RM-0.1..0.4), packaging fix (RM-0.5), onboarding
truth (RM-0.6). *(License: dropped per owner — personal project.)*

**M1 [Track P] — Part 1 true: the MH auto-sequencer works as designed**
Golden harness first (RM-1.0) → render-repair campaign (RM-1.1, one golden-diffed
branch) → channel defaults (RM-1.2) → audio truth campaign (RM-1.3) →
instrumentation + cache identity (RM-1.4) → eval writer restored + first committed
evaluation with a human judgment (RM-1.6) → delivery v1: `.xtiming` + fresh
`.xsq`/`.xmap`, template-merge retired ⚖, xLights acceptance test in CI.
*Exit:* a song renders to a correct, importable MH show; the system can measure and
remember what it produced; the CLI takes the user's fixture config (no hardcoded
rig).

**M2 [Track P] — Creative quality, measured**
Plan schema v2 + template channel parameters + data-first loader; lyric MomentCues
wired; macro structured contract (D3); judge repair (D4); deterministic selector
arm; the three-arm blind-eval gate (D1's standing default); stems (D8); model
retarget + structured outputs (D6, deadline-driven).
*Exit:* an evidence-backed answer to whether the LLM makes better MH shows, and a
plan schema rich enough to carry learned display grammar in M3.

**M1-K [Track K, parallel with M1] — The loop's edges**
Content-hash identity (edge 1); active-learning corrections wired (edge 3);
recipe-generation calls into the provider framework; catalog-in-repo decision
implemented (D9): seed catalog committed (initial content: the existing builtin
recipes + a first curated mining pass over the author's local corpus).
*Exit:* re-ingesting the same corpus is idempotent; a taxonomy correction made by a
human demonstrably changes the next mining run; a versioned catalog exists in git.

**M2-K [Track K] — Grammar at usable scale**
Mining passes over the available corpus → recipe_builder curation sessions (mined +
LLM-generated arms) → catalog grows with propensity/affinity data per element type;
quality gates tuned; style fingerprints for the author's preferred styles.
*Exit:* the catalog answers "what does a megatree do at a chorus / arches at a drop /
icicles under a verse" with admitted, layout-conditioned recipes — measured by
coverage: every element type in the author's layout has BASE/RHYTHM/ACCENT options
across the energy range.

**M3 [Tracks converge] — Part 2: the show choreographs**
Display composition repairs (P5 cluster); display pipeline CLI-reachable, consuming
the catalog + macro arc + the user's layout (the propensity-conditioned apply edge —
edge 2 closed); MH + display coordinated by the shared macro contract; unified
export core; automation-API injection workflow.
*Exit:* one command, one song, the user's layout → a coordinated MH + display show
built from **learned** choreography, importable into xLights; evaluation results +
human judgments recorded and feeding the loop (edge 4 → D5(d) begins).

**M4 — Compounding** *(ongoing)*
ML/Python bump (D7); MH mining exploration (vendor packs contain DMX moving-head
sequences — the deleted-history artifact was literally one — so extending the miner
to MH idioms is plausible and would begin unifying part 1 with the knowledge loop);
style transfer when the catalog justifies ranking; debt retirement per recorded
sequencing constraints; documentation truth pass.

## 5. Risks and honesty checks

- **Corpus availability is the knowledge track's pacing item**: mining quality is
  bounded by what's locally available to learn from. Mitigation: the LLM-generation
  arm and seeds keep the catalog moving; M2-K's exit is defined by coverage, not by
  corpus size.
- **Weak supervision remains partially circular until enough human corrections
  accumulate** (edge 3 wired ≠ labels fixed overnight). Honest metric: track
  correction-driven label changes per mining run.
- **Template re-authoring scale (M2)**: mitigated by the data-first loader and the
  MH-template≈recipe convergence — re-authoring is also catalog seeding.
- **Single maintainer**: the two tracks are independently pausable; every milestone
  exits at a usable state.
- **Empirical unknowns** (cheap, front-loaded): bare-`.xsq` import without
  rgbeffects; `json_object` on 5.6; physical shutter mapping (channel-6/17 test).
- **What would change this plan**: blind eval flipping D1's default (absorbed by
  design); the catalog failing M2-K's coverage exit despite both supply arms (would
  force rethinking recipe granularity — the honest fallback, stated now, is
  coarser-grained learned *style profiles* steering hand-seeded recipe families);
  xLights shipping an actual external choreography hook (re-rank D2c upward — verify
  against release notes, never assume).

## 6. Non-goals

No rewrite; no provider swap; no UI product; no commercialization scaffolding
(licensing, distribution, marketplaces) unless the owner's intent changes; no
deletion of the learning system — its four edges get repaired, its supply arms get
exercised, and its output finally reaches a show.
