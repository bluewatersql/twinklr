---
type: change
status: complete
area: reference
created: 2026-11-12
updated: 2026-11-12
---

# Moving-head true-up research

## Goal and authorization

Investigate xLights' Tools → Generate Moving Head Effects, identify transferable
capabilities, compare other moving-head sequencers, and synthesize a prioritized,
phased recommendation grounded in Twinklr's current implementation.

Owner instruction: research/analysis only, use this folder, disregard current
workstreams, and do not change project code. Existing workstream priorities are not
dependencies for this analysis. Existing implementation and accepted behavior remain
the baseline, not an authorization to alter them.

## Scope and acceptance

- Trace xLights UI, generation algorithms, timing/section handling, emitted effects,
  motion/pattern engine, limits, version provenance, and relevant reuse boundaries.
- Audit tracked Twinklr moving-head source, schemas, tests, and durable decisions.
- Compare primary-source evidence for open-source and commercial sequencing tools;
  distinguish documented behavior from inaccessible proprietary internals.
- Deliver one comprehensive `report.md` with citations, gap/transfer matrices,
  differentiators, implementation directions, dependencies, and phase exit criteria.
- Leave a handoff with actual checks and unresolved evidence/owner decisions.

## Non-goals and boundaries

No application code, runtime configuration, schemas, fixtures, or existing workstream
plans change. No paid provider calls, owner-local media/layout/corpus access, live
xLights mutation, or claimed human visual acceptance. Public upstream source and
official documentation are permitted research inputs. Recommendations are proposed,
not accepted architecture or verified performance claims.

## Research plan and ownership

The integrator owns all edits in this change folder on `chore/knowledge-optimization`.
Baseline checkout was clean. Research-skill background investigators read repository
context and public primary sources only; each writes a separate temporary Markdown
memo outside the repository. They do not edit this working tree or change Git state.

1. Integrator: xLights source tracing and final synthesis.
2. Background investigator: other sequencing products and open-source projects.
3. Background investigator: tracked Twinklr capability/gap audit.
4. Independent review: report claims, source links, scope, and phase coherence.

Relevant source areas: `packages/twinklr/core/sequencer/moving_heads/`, `curves/`,
`formats/xlights/`, planner models, tracked fixture abstractions, and tests.

## Validation

Check source/version provenance, report coverage of all five requests, citation and
local-link integrity, and final Git diff scope. The repository's full `make validate`
gate is not assumed to pass: it requires a clean committed tree and rewrites code;
if omitted for this research-only session, explicitly disclose that limitation.
No empirical or taste conclusions follow from document checks.

The report is a proposed research deliverable. No current-truth promotion is warranted
until review and an owner decision; existing workstream records remain untouched as
requested.

## Delivery

Research delivered in [report.md](report.md); independent [review](review.md) approved
the research with no material findings. The roadmap remains proposed. Source experiment
and limitations are in [evidence.md](evidence.md); continuation is in [handoff.md](handoff.md).
