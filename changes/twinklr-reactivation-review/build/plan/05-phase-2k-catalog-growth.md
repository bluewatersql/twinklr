# Phase 2K — Catalog Growth (M2-K)

_Goal: the catalog reaches usable choreographic coverage for the author's layout,
grown by both supply arms through human curation. Mostly human-in-the-loop sessions
orchestrated by tooling built in 1K — this phase is data work, with small tooling
tasks. Runs parallel to 2P after 1K. Proposal M2-K; D5._

> **Status — 2026-08-14:** tooling for T1–T4 is merged and independently verified.
> This is a **tooling implementation milestone, not Phase 2K completion**. The phase
> remains owner/data-gated on the author's real layout, local corpus, curation
> decisions, and preferred-style declarations. The current snapshot and continuation
> order are owned by [HANDOFF.md](HANDOFF.md).

**Exit criteria (coverage-defined, not corpus-size-defined):** every element type in
the author's layout has admitted BASE/RHYTHM/ACCENT recipe options across the energy
range; propensity/affinity data populated per element type; style fingerprints exist
for the author's preferred styles; catalog versioned in git with provenance.

## Tasks

| ID | Title | What (summary) | Evidence | Deps | Executor | Verifier |
|---|---|---|---|---|---|---|
| P2K-T1 | Coverage report tooling | A `catalog coverage` command: element-type × role × energy matrix from the tracked catalog + the user's layout; gaps ranked; drives every curation session and defines this phase's exit. | D5, M2-K exit | P1K-T3 | sonnet | sonnet |
| P2K-T2 | Mining runs over available corpus | Full FE pipeline runs over the author's local corpus with content-hash identity; mined candidates staged; quality-gate thresholds reviewed against real support/stability distributions (the hand-tuned constants get their first empirical look). | D5(c), P6 quality-gate notes | P1K-T1..T4 | sonnet | opus |
| P2K-T3 | LLM-generation curation sessions | recipe_builder generation arm (now in the provider framework, sol-tier) targeted at T1's coverage gaps; staged → human admission sessions; per-session log of admit/reject reasons feeds prompt refinement. | D5(b) | P1K-T4/T5, P2K-T1 | sonnet | sonnet |
| P2K-T4 | Style fingerprints + propensity refresh | Fingerprint extraction over the curated corpus for the author's preferred styles; propensity index rebuilt with stable identities; both verified consumable by the display planner context (the apply edge's data half, ahead of Phase 3's code half). | D5, group_planner context evidence | P2K-T2 | sonnet | opus |

## Notes for spec authors

- This phase's "executor" for T2/T3 sessions is really the OWNER plus tooling; specs
  define the tooling + session protocol, not autonomous agent authoring of taste.
- Coverage exit is per the AUTHOR'S layout first (design center), not universal.

## Tooling implementation record — 2026-08-14

- P2K-T1 coverage report tooling — `25ea555`
- P2K-T2 corpus mining/distribution and threshold-review tooling — `1bd56c3`
- P2K-T3 targeted generation and human-admission tooling — `df2b295`
- P2K-T4 style-group fingerprints, propensity refresh, and selection plumbing — `64bc4d1`

All four tooling changes are merged and independently verified in the integrated
`6b2b34a` snapshot. They make the real-data sessions reproducible; they do not supply
their outcomes. Phase exit still requires zero layout coverage gaps, an idempotent real
corpus run plus owner-authored threshold decision log, live generation/admission
sessions, and owner-declared style fingerprints with refreshed propensity verified in
the planner path. None of those taste- or private-data-bearing results is claimed here.
