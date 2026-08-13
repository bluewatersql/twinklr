# Phase 2K — Catalog Growth (M2-K)

_Goal: the catalog reaches usable choreographic coverage for the author's layout,
grown by both supply arms through human curation. Mostly human-in-the-loop sessions
orchestrated by tooling built in 1K — this phase is data work, with small tooling
tasks. Runs parallel to 2P after 1K. Proposal M2-K; D5._

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
