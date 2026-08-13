# P2K-T2 — Mining runs over available corpus

⚖ **Owner-decision-bearing.** This task's executor role is the OWNER running
tooling, not an autonomous agent making taste/quality calls. The agent's job is to
build/harden the tooling and produce the empirical evidence; the owner reviews the
evidence and makes the threshold decisions. Do not have an agent silently change
`FeatureEngineeringPipelineOptions` quality-gate defaults as part of this task — the
deliverable is a **decision log**, and any threshold change is the owner's explicit
choice recorded in that log, not a code change an agent decides on its own.

Phase: 2K (M2-K) · Lane: — · Executor: sonnet (tooling) + OWNER (session) ·
Verifier: opus · Depends on: P1K-T1..T4

## Objective

Run the full feature-engineering mining pipeline over the author's local corpus with
content-hash identity (post P1K-T1), stage the mined candidates, and — separately —
produce an empirical distribution report of the hand-tuned quality-gate constants
(support counts, cross-pack stability) against what the real corpus actually
produces, with a decision log recording whether each constant is kept, and why.
This is explicitly the constants' first look against real data; no prior evaluation
of them exists.

## Evidence & background

- Plan task (`build/plan/05-phase-2k-catalog-growth.md:18`): "Full FE pipeline runs
  over the author's local corpus with content-hash identity; mined candidates
  staged; quality-gate thresholds reviewed against real support/stability
  distributions (the hand-tuned constants get their first empirical look)."
- **The hand-tuned constants list (verified, all four sites)**:
  1. `recipe_promotion_min_support: int = 2`,
     `recipe_promotion_min_stability: float = 0.015`
     (`packages/twinklr/core/feature_engineering/config.py:135-136`) — the
     **actually-configured, pipeline-wide values**.
  2. `PromotionPipeline.run()`'s **own hardcoded parameter defaults** are
     `min_support: int = 5`, `min_stability: float = 0.3`
     (`packages/twinklr/core/feature_engineering/promotion.py:103-104`) — nearly
     an order of magnitude stricter than what `config.py` actually configures
     system-wide. **This gap between the pipeline's own "sane default" and its
     configured value is itself a finding worth putting in front of the owner** —
     it was not previously flagged in the review (P6) as a discrepancy, only each
     number individually as "empirically tuned... with no comment citing how they
     were chosen."
  3. `_MIN_SUPPORT = 3` and `_ANTI_AFFINITY_THRESHOLD = 0.05` in
     `feature_engineering/propensity.py:39,42` — corpus support required to emit a
     propensity affinity/anti-affinity at all.
  4. The `0.35` role-score cutoff in `TargetRoleAssigner._assign_one()`
     (`feature_engineering/taxonomy/target_roles.py:191`, `if ranked and
     ranked[0][1] >= 0.35:`).
  5. `recipe_promotion_max_per_family: int = 10`,
     `recipe_promotion_max_per_cluster: int = 2` (`config.py:138,141`) — caps, not
     gates, but likewise untuned against real distributions.
- **Adaptive stability already exists and is in scope for review, not
  reinvention**: `_adaptive_stability(median_distinct_pack_count, lower_bound=0.03,
  upper_bound=0.9)` (`promotion.py:40-67`) log-scales an effective stability
  threshold from corpus diversity, used when `recipe_promotion_adaptive_stability =
  True` (`config.py:137`, on by default). The promotion report already carries
  `effective_min_stability`/`effective_min_support`
  (`promotion.py:275-276` region) — this task's distribution report should surface
  these effective values per run, not just the static config constants, since
  adaptive stability means the real gate the corpus experienced may differ from the
  static `0.015`.
- P6 finding (`reviews/phases/corpus-intelligence.md:308-316`): "(1) several of the
  numeric constants driving lane-inference and gating... read as empirically tuned
  rather than derived, with no comment citing how they were chosen or against what
  evaluation set; (2) `cross_pack_stability`/`support_ratio` are simple ratios with
  no statistical-significance adjustment for sample size — a template supported by
  3 instances in 1 pack can pass the same numeric gate shape as one supported by 300
  instances across 20 packs, differentiated only by the ratio's face value." This
  task's distribution report must make that specific failure mode visible (report
  the pack-count distribution alongside the raw ratio, not just the ratio).
- P6-M2 (content-hash identity) is the precondition this task depends on via
  P1K-T1: re-running mining over an unchanged corpus must now be a no-op/dedup, not
  an accumulation of duplicate rows — verify this holds before trusting any
  distribution numbers this task produces (duplicate rows would silently inflate
  every support count).
- D5(c) (`reactivation-proposal.md:159-163`): mining is one of two supply arms into
  the curated catalog; nothing here auto-promotes — staged only, same as
  `recipe_builder`'s own safety language (`pipeline.py:113-118`,
  `"NOTE: All outputs are staged only — not merged into the live library."`).

## Current behavior

- The mining pipeline entry point is `FeatureEngineeringPipeline` +
  `FeatureEngineeringPipelineOptions`
  (`packages/twinklr/core/feature_engineering/pipeline.py`,
  `feature_engineering/config.py`), driven today only via
  `scripts/demo_feature_engineering.py` (no CLI/Makefile entry — confirmed absent
  in P6's scope survey). It builds a `ProfileCorpusBuilder` corpus from
  `data/vendor_packages` (default, `config.py:93`) and `data/music`
  (`config.py:94`), then runs taxonomy → template mining → recipe promotion
  (`corpus_artifacts.py::run_recipe_promotion`, `corpus_artifacts.py:375-445`) →
  writes `recipe_catalog.json` and related artifacts.
- **No documented single-command orchestrator exists.** `docs/pipeline_guide.md`
  references a `scripts/build/build_pipeline.py` that does not exist anywhere in
  the repo (confirmed by `find`, P6 finding) — running the corpus pipeline today
  means manually chaining `demo_profiling.py` → `demo_feature_engineering.py` (and
  optionally `demo_recipe_pipeline.py`) with matching paths by hand.
- `PromotionPipeline.run()` already returns a `PromotionResult` with a `report:
  dict[str, Any]` (`promotion.py:70-76`) that includes acceptance/rejection counts
  and effective thresholds — but nothing today aggregates the **full distribution**
  of `support_count`/`cross_pack_stability` across all candidates (passed and
  rejected) into a reviewable report; only the pass/fail outcome per threshold is
  visible.

## Target behavior

Two deliverables, run as one owner session using tooling this task builds/hardens:

1. **A hardened, documented mining-run command** (building on
   `scripts/demo_feature_engineering.py`, not replacing it wholesale) that: runs the
   full FE pipeline over `data/vendor_packages`/`data/music` (or owner-supplied
   paths) with content-hash identity in effect (post P1K-T1 — verify P1K-T1 has
   actually landed and re-profiling an unchanged archive is idempotent before
   relying on any count from this run); stages mined candidates (does not
   auto-promote — matches existing `recipe_builder` safety posture, this pipeline's
   own promotion step already writes to a distinct output, not the live
   `data/templates` catalog, unless explicitly pointed there); and produces a run
   manifest recording exactly which corpus paths were used and the resulting
   artifact locations, so the session is reproducible and auditable.
2. **A quality-gate distribution report** — a new report (JSON + human-readable)
   that, for a completed mining run, shows:
   - The full histogram of `support_count` and `cross_pack_stability` across ALL
     mined `MinedTemplate` candidates (not just the ones that passed), bucketed
     coarsely enough to be readable by eye.
   - For each of the 5 hand-tuned constants listed above: the configured value, the
     count of candidates that would pass/fail at that exact value, and — where
     adjacent values are meaningfully different — how the pass/fail count changes
     at a couple of nearby values (e.g. `min_support` at 2/3/5, `min_stability` at
     0.015/0.05/0.3) so the owner can see the real sensitivity, not just a single
     point.
   - The `distinct_pack_count` distribution alongside `cross_pack_stability`,
     specifically to surface P6's flagged failure mode (low-pack-count templates
     passing on ratio alone).
   - The `effective_min_stability`/`effective_min_support` actually applied per run
     when `recipe_promotion_adaptive_stability=True`, distinct from the static
     config constants.
   - The `promotion.py:103-104` vs `config.py:135-136` discrepancy (5/0.3 vs 2/0.015)
     called out explicitly as a line item for the owner to resolve, not silently
     reconciled by the agent.
3. **A decision log** (a dated Markdown file, one entry per constant reviewed)
   recording: the constant, its current value, the empirical distribution evidence
   from (2), the owner's decision (keep / change to X / defer — needs more corpus),
   and the reasoning. This is a human-authored artifact captured during the session,
   not agent-generated prose describing what the owner "should" decide.

## Implementation approach

- Tooling module: extend `scripts/demo_feature_engineering.py` or add a sibling
  `scripts/report_quality_gate_distributions.py` — whichever keeps the existing demo
  script's role (running the pipeline) separate from the new reporting role
  (analyzing candidate distributions after a run). Do not fold distribution
  reporting into `PromotionPipeline.run()` itself — that class's job is gating, not
  reporting; build the distribution report as a separate consumer of the same
  `MinedTemplate` candidate list `PromotionPipeline.run()` already receives as input,
  run in read-only/report mode alongside (not instead of) the real gated run.
  Follow this phase's CLI convention set by P1K-T4 (recipe_builder becoming a
  first-class command) if that lands first — re-verify.
- The decision log lives under `changes/twinklr-reactivation-review/` or a
  phase-2K-specific home the orchestrator designates at merge time — do not put it
  in `memories/` directly (it's an active-phase working artifact, not yet a durable
  cross-project lesson); if the constants DO change as a result, that change (with
  its rationale) is exactly the kind of decision that belongs in `memories/decisions/`
  once accepted — file it there per `AGENTS.md`'s memory protocol at phase close,
  not mid-session.
- If the owner decides to change a constant, the actual code change (`config.py`
  edit) is a small, separate, explicitly-approved diff — do not bundle an
  unreviewed threshold change into the same commit as the tooling build.

## Acceptance criteria

- [ ] A mining run completes over the author's real local corpus (or, if none is
  available on the execution machine, a documented fixture corpus — state which,
  loudly, in the run manifest) and produces staged candidates plus a run manifest.
- [ ] Re-running the mining command a second time over an unchanged corpus produces
  no new/duplicate rows in the feature store (this is the acceptance signal that
  P1K-T1's content-hash identity actually landed and holds under this task's real
  usage, not just its own unit tests).
- [ ] The distribution report shows real histograms (not zero-candidate/empty
  output) for `support_count` and `cross_pack_stability` across all mined
  candidates.
- [ ] Each of the 5 named constants has a corresponding entry in the distribution
  report showing pass/fail sensitivity at the configured value and at least two
  nearby values.
- [ ] The `promotion.py` vs `config.py` default discrepancy is called out explicitly
  in the report.
- [ ] A decision log exists with one dated entry per constant, each recording a
  keep/change/defer decision and its rationale, authored during the owner's session
  (not fabricated post hoc by an agent).
- [ ] No live catalog file (`data/templates/index.json` or its P1K-T3 successor
  location) is modified by this task — mining output stays staged, matching
  existing `recipe_builder`/FE promotion safety posture.

## Tests

- Unit test: the distribution-report builder against a small synthetic list of
  `MinedTemplate`-shaped candidates with known support/stability values, asserting
  the histogram buckets and the sensitivity table at chosen nearby values match
  hand computation.
- Unit test: idempotent-rerun assertion — run the mining pipeline stage twice over
  an identical tiny fixture corpus (already used by P1K-T1's own tests if
  available — reuse rather than build a second fixture) and assert row counts in the
  feature store do not grow on the second run.
- No test asserts a "correct" value for any of the 5 constants — that is the
  owner's decision, not a pinned behavior.

## Verification commands

```bash
uv run mypy scripts/demo_feature_engineering.py scripts/report_quality_gate_distributions.py
uv run ruff check scripts/ packages/twinklr/core/feature_engineering/
uv run pytest tests/unit/feature_engineering/test_quality_gate_distributions.py -q
uv run python scripts/demo_feature_engineering.py --corpus-dir <author-local-corpus>  # LOCAL-ONLY: real vendor corpus required, not fixture-safe for CI
uv run python scripts/report_quality_gate_distributions.py --run-dir <mining-run-output>  # LOCAL-ONLY: depends on the above
```

## Effort & risk

**L**, owner-session-gated. Main risk: no local corpus may exist on the execution
machine at task time (P6 noted `data/vendor_packages` is gitignored and absent from
the reviewed checkout) — mitigation is to build and unit-test the distribution-report
logic against synthetic fixtures so the tooling is verified independent of corpus
availability, and to state clearly in the run manifest/handoff whether the real
mining run against the author's actual corpus happened or is still pending the
owner's local session. Secondary risk: conflating "build the reporting tool" with
"decide the thresholds" — the acceptance criteria above are written to keep those
separated; a verifier should reject any diff that changes `config.py` constants
without an accompanying dated decision-log entry.
