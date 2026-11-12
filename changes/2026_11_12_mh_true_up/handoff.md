---
type: handoff
status: complete
area: reference
created: 2026-11-12
updated: 2026-11-12
---

# Moving-head true-up research handoff

## Start here

Read [report.md](report.md), the single synthesized analysis. It covers the xLights
generator's source-level behavior, transferable mechanisms, Twinklr's implemented
baseline and gaps, nine external projects/products/standards, proposed differentiators,
and a prioritized P0–P5 roadmap. The roadmap is proposed, not accepted implementation.

Research is complete. Independent [review](review.md) approved it with no material
findings; this is not owner acceptance of the proposed roadmap. No project code,
runtime configuration, schema or fixture was changed.

## Scope and decisions

- Owner requested research only in `changes/2026_11_12_mh_true_up`, disregarding current
  workstreams. All repository edits are confined to this folder. No existing active
  workstream record or `changes/ACTIVE.md` row was changed.
- The report distinguishes the sparse xLights song generator from its broader native
  Moving Head renderer. Three key source files match the released `2026.19` versions.
- Recommendations prioritize fixture/channel correctness, dark pre-positioning and
  controllable composition. Existing templates, selector, preview, regeneration and
  whole-show coordination are retained as foundations.
- Current accepted render behavior is a migration constraint. Proposed opt-in/versioned
  semantics do not authorize changing that behavior.
- Existing context/memories were read; no promotion was made because this is proposed
  research and no architecture, owner decision or empirical product outcome changed.
- The research skill called for background investigation. Two read-only investigators
  wrote separate temporary memos; only the integrator edited repository documents.
  Independent review uses a separate context and a temporary review memo.

## Versions and branch

Branch: `chore/knowledge-optimization`. Initial source: `ab1e1457c8b524706f9ebaa55e65af2b743bfb07`.
Audited application source: `2d1af61d69a0acc1b5dd877dd64459d9fbfb0f3f`.
An independent later commit `9c55c2e72c4bfea30a5ab7ae197579e4feb74485` regenerated
goldens only; it did not change the audited application source. No commit, push or PR
was made by this research session. Recheck HEAD before future implementation.

xLights source: `fe78fdddb7524cea71ee4c2ac4c22e20c16d478f`; introduction release `2026.19`.
QLC+ source: `167da48141c60d820cd715f52bb535ad1cc0ecc1`.

## Validation and evidence

- [evidence.md](evidence.md) records source hashes, release/source cross-checks, exact
  isolated compile/probe command, observed output, and the complete reproduction probe.
- The wx-free xLights generator compiled with C++17, warnings enabled, and exited zero
  on synthetic tests of Peak-only behavior, selected-head stability and insufficient
  dark travel. This is not an xLights application or hardware test.
- Static AST counts independently confirmed 37 builtin templates, 30 movement entries,
  18 geometry entries and six dimmer entries (enum counts include NONE).
- Reference checking found and then corrected one missing `XWiki` definition. The next
  pass resolved 44 references and checked 35 local links, with the handoff initially
  pending creation. Final all-file checks are recorded below.
- `make validate` was **not run**: it requires a clean committed tree and rewrites
  format/lint output, while the owner requested research only. No test-suite success
  or runtime acceptance is claimed.
- No owner-local media/layout/corpus, paid/live provider calls, running-show mutation,
  hardware tests or human taste judgments were performed.

## Files

Created: `brief.md`, `report.md`, `evidence.md`, `handoff.md`, `review.md`.
No existing tracked file was modified or deleted by this research.

## Final document checks

The document checker resolves relative links and report reference definitions, checks
balanced code fences, rejects unfinished HTML placeholders, and checks trailing
whitespace with `git diff --no-index --check /dev/null <file>` for each new Markdown
file. The initial wrapper incorrectly expected exit zero from no-index comparison of
a new file; it was corrected to accept the normal difference status (1) only when
there are no diagnostic lines. No whitespace defect was reported by that command.
The corrected final check passed for all five files.

Final `git status --short --branch`: only this new research folder was untracked;
no existing tracked file had local modifications. No changes were staged or committed.

## Next action

Read the recommendations and choose the first implementation scope, likely P0 followed
by the P1 fixture/transition foundation and a small P2 effect set. A future accepted
brief should specify compatibility, initial fixture profiles, infeasibility fallback,
and measurable exits. Real music/provider/hardware work needs its own authorization;
human/physical outcomes remain **PENDING-OWNER**. No action is required to keep using
the existing implementation.
