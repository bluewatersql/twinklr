# P4-T7 — MH-idiom mining exploration (optional)

Phase: 4-compounding · Lane: mh-mining-spike (read-mostly; writes only a decision
memo under `changes/` or `memories/` per the memory protocol — see Deliverable) ·
Executor: opus · Verifier: opus · Depends on: P2K-T2 (per
`changes/twinklr-reactivation-review/build/plan/07-phase-4-compounding.md` task table)

⚖ **Owner-decision-bearing, and explicitly optional.** This task's entire output is a
decision memo the owner reads and acts on later — it is not itself a feature, and it
must not become one. If the spike's time-box is consumed and the feasibility question
is still open, the correct outcome is "inconclusive, here's what's needed to know
more" — not an unfinished MH-mining implementation left half-wired in the tree.

## Objective

Determine, within a fixed time-box, whether the corpus-intelligence mining pipeline's
propensity/taxonomy/stack extraction — proven (by P2K-T2) against display sequences —
can meaningfully extract the equivalent idioms (which movement/preset patterns belong
on which fixture role, at which moment, in which style) from DMX moving-head vendor
sequences. Produce a decision memo answering: is this worth building, and if so,
roughly how, and what would it unblock.

## Evidence & background

**Plan table entry** (`07-phase-4-compounding.md` P4-T7 row): "Feasibility spike:
extend the miner to DMX moving-head sequences in vendor packs (the deleted-history
artifact proves they exist); if propensity/idiom extraction works for MH, part 1
joins the knowledge loop (one catalog, two renderers, completed). Time-boxed;
outcome = a decision memo, not a feature."

**Phase notes** (`07-phase-4-compounding.md` "Notes for spec authors"): "T7 is
deliberately last and optional — it must not leak scope into earlier phases."

**D5 — Knowledge supply** (reactivation-proposal.md:159–162, unchanged from v2):
"mining + LLM generation as complementary arms into one curated catalog; seeds from
hand-authoring; evaluation feedback as the fourth arm once D11 lands." The knowledge
loop as designed (§1 of the proposal) is display-oriented in its worked description
— this task asks whether the SAME loop generalizes to moving heads, which today
learn nothing from mined sequences (the MH path is templates authored by hand, per
`moving-heads-rendering.md`'s 37-hand-authored-templates finding, not corpus-derived).

**"One catalog, two renderers" convergence framing** (reactivation-proposal.md §1,
the ACQUIRE→LEARN→CURATE→CATALOG→PLAN→RENDER→EVALUATE loop description, and §2.1's
target-architecture table): the project's target architecture already treats
Knowledge as one system feeding Performance, and Performance as "plan → render →
deliver" with MH and display as the two renderers under that one plan. This task
tests whether Knowledge's ACQUIRE/LEARN stages can also feed the MH renderer instead
of MH remaining permanently hand-authored-only — this is what "part 1 joins the
knowledge loop... completed" means: today only part 2 (display) is designed to learn
from mined data.

**Existing mining pipeline evidence (re-verify against current tree, this task runs
after P2K-T2 has exercised it for real against display sequences):**
`profiling/discovery.py:16-25`'s `discover_vendor_archives(vendor_root)` recursively
scans `<vendor_root>/<vendor>/` for `.zip`/`.xsqz` archives, namespaced by named
third-party vendor (`corpus-intelligence.md:658-660`) — this scanning mechanism is
generic to xLights sequence archives and is not obviously display-only; whether the
DOWNSTREAM feature-extraction (propensity, taxonomy, stack mining) that operates on
what's inside those archives is display-specific or could target MH effect data
instead is exactly this spike's question.

**Vendor-pack MH sequences exist claim**: the plan row cites "the deleted-history
artifact" as proof MH vendor sequences exist to mine. Re-verify this claim yourself
before relying on it — do not take the plan's summary as sufficient evidence for a
decision memo; check git history (`git log --all --diff-filter=D` on relevant paths,
similar to the archaeology method `verification.md`'s P6-F3 section used for the
checkpoint-writer discovery at commit `b6fdfd2`) for any deleted MH-specific vendor
archive references or fixtures, and check `product-and-approach.md:64`'s "the real
rig, visible in deleted history (`b6fdfd2`): four moving heads, one song, one yard"
for what that commit actually shows about vendor-sourced MH content versus
hand-authored content for the owner's own rig — these may be different things (the
owner's own show vs. third-party vendor MH sequences) and the memo must not conflate
them.

**Licensing note (inherited context, do not re-litigate):** D5/D9's licensing framing
(reactivation-proposal.md §0.4: "Licensing de-escalated to a footnote... personal
project") applies here too — this is exploratory analysis of vendor content already
governed by the corpus pipeline's existing "don't redistribute vendor-derived
content" courtesy rule (reactivation-proposal.md's "Fixed constraints from the
owner" section). Nothing in this spike authorizes redistributing any mined MH
content; it stays local, same as the existing display-mining corpus.

## Current behavior

The corpus-intelligence mining pipeline (propensity extraction, phrase taxonomy,
template/stack mining with support gates) operates on display sequence data only.
Moving-head templates are 37 hand-authored Python definitions
(`moving_heads/templates/builtins/*.py`) with no path from mined vendor content into
the MH template library. `P2K-T2` will have run the display-side FE pipeline against
the author's real local corpus for the first time by the time this task starts,
giving this spike real, non-synthetic data to reason from about what mining actually
produces.

## Target behavior

A single decision memo exists (see Deliverable) answering, with evidence gathered
during the time-box:

1. **Do DMX moving-head vendor sequences exist in the author's accessible corpus in
   sufficient quantity/variety to mine?** (Re-verified claim, not assumed from the
   plan summary.)
2. **Can the existing propensity/taxonomy/stack-mining logic be pointed at MH effect
   data with a reasonable adapter**, or does MH's fundamentally different effect
   model (pan/tilt/dimmer/color/gobo/shutter curves + preset+movement-template
   structure, vs. display's per-pixel/per-model effect layering) require a
   substantially different feature-extraction approach? Cite specific code you
   examined (`profiling/`, `feature_engineering/`) and specific MH data structures
   (`moving_heads/templates/`, `curves/`) to ground the answer in actual shapes, not
   abstract compatibility guessing.
3. **If feasible, what's the rough shape of the work** (new feature extractors, a
   different taxonomy for MH idioms vs. display idioms, template/stack mining
   changes) and roughly how it compares in size to what P2K-T2/T3/T4 built for
   display — enough for the owner to size a future task, not a full implementation
   plan.
4. **If not feasible (or not worth it), why**, and what would have to change
   (more/different corpus data, a redesigned MH template representation) to revisit
   the question later.
5. **Recommendation**: pursue now, pursue later with named triggers, or don't pursue
   — matching the pattern D5 uses elsewhere in the proposal for parked capabilities
   ("`style_transfer` and embedding upgrades parked with explicit triggers").

**Non-goals:** implementing any MH mining code. Modifying the display-side mining
pipeline. Modifying MH templates. Running mining against vendor content without
first confirming (step 1) that such content is actually available to test against —
if it isn't, the memo's answer to the feasibility question is itself "no accessible
test data," which is a valid and useful conclusion, not a task failure.

## Implementation approach

This is research/analysis work, not implementation. Suggested approach within the
time-box (see Effort & risk for the box itself):

1. Re-verify vendor MH sequence availability (git archaeology + current
   `data/vendor_packages`-equivalent directories, gitignored but possibly present
   locally in the owner's environment — check, don't assume absence just because
   nothing is tracked in git).
2. Read the mining pipeline's feature-extraction code
   (`feature_engineering/`, `profiling/`) closely enough to characterize what
   structural assumptions it makes about display sequences that may or may not hold
   for MH effect data (e.g., does it key on per-model/per-element identity in a way
   that has a clean MH analogue — fixture/channel identity — or does it assume
   pixel-level density patterns that have no MH equivalent).
3. If real MH vendor data is available, attempt the smallest possible experiment:
   parse a handful of MH sequences' effect data into whatever intermediate
   representation the display miner consumes, and see how far existing code gets
   before hitting a structural wall. This is exploratory scripting for the spike's
   own use, not a deliverable — do not polish it into shipped code, and do not leave
   throwaway scripts in the tracked tree (scratch it, or if genuinely useful,
   name it as a prototype explicitly in the memo with a note that it's
   spike-quality, not production).
4. Write the memo.

## Deliverable

A decision memo, not code. Per `AGENTS.md`'s change-management protocol, this
belongs under `changes/<slug>/` if it's substantial enough to track as its own
artifact (recommended: a short-lived `changes/mh-idiom-mining-feasibility/` with a
single memo file), or as a durable memory entry under `memories/` if the finding is
better framed as a standing decision record (e.g.,
`memories/decisions/mh-idiom-mining-<verdict>.md`) per the memory protocol —
executor's judgment on which fits better, but it must land in one of these two
canonical homes, not as a loose file outside the knowledge-placement table in
`AGENTS.md`. Update the relevant `INDEX.md` per the protocol.

## Acceptance criteria

- The memo directly answers all five questions under Target behavior, each with
  cited evidence (file paths, specific data examined, or an explicit "could not
  verify, here's why" if data access was the blocker).
- The vendor-MH-sequence-availability claim from the plan row is independently
  re-verified (confirmed, refuted, or genuinely inconclusive) rather than repeated
  on the plan's authority alone.
- No MH mining code, template changes, or display-pipeline changes ship as part of
  this task — `git diff` against the tree (excluding the memo file itself and any
  explicitly-labeled spike-quality prototype script, if the executor chooses to keep
  one) shows no application-code changes.
- The memo states a clear recommendation (pursue now / pursue later with named
  triggers / don't pursue), not an open-ended "more research needed" non-answer —
  if the time-box genuinely wasn't enough to reach a recommendation, the memo says
  so explicitly and names what additional time/data would be needed, which IS an
  acceptable form of "clear recommendation" for a time-boxed spike.

## Tests

Not applicable — this is a research spike producing a document, not code. If a
spike-quality prototype script is kept (per Implementation approach, step 3), it
does not need test coverage; label it as such explicitly wherever it lives so it is
never mistaken for production code.

## Verification commands

```bash
git diff --stat main   # confirm no application-code changes beyond the memo/prototype
```

The verifier's job for this task is primarily an evidence-quality review of the
memo — does every claim trace to something the executor actually examined, per this
spec's re-verification instructions — not a code-correctness review.

## Effort & risk

**S, time-boxed.** Recommend capping this at the equivalent of one focused working
session (the plan and phase notes are explicit that this must not leak scope into
earlier phases or balloon into a de facto feature task). Main risk is exactly that
scope creep — an opus-tier executor finding the mining pipeline "almost works" for MH
data may be tempted to keep going past the box to prove it out fully. Mitigation:
the deliverable is explicitly a memo, and the acceptance criteria explicitly forbid
shipping application-code changes — if the spike produces working code, that outcome
belongs in the memo's recommendation ("here's a working prototype, sized at X, next
task should formalize it"), not in this task's merged diff.

## Execution status — 2026-08-26: NO-GO / deferred

Only a safe prerequisite preflight was performed. P2K-T2's tooling is integrated, but
its owner/data-gated acceptance evidence is not: no accepted real-corpus mining run,
idempotent rerun result, non-empty support/stability distributions, or owner-authored
threshold decision log exists. A filename-only scan of the accessible local `data/`
paths found no MH corpus manifest and no `.xsq`, `.xsqz`, or vendor archive; a scoped
repository filename scan likewise found no moving-head corpus manifest. No corpus
content was opened, parsed, or mined, and no network/live/provider action occurred.

Full execution is therefore **NO-GO and deferred** until both prerequisites exist:

1. P2K-T2's empirical owner-corpus exits are accepted.
2. An accessible, provenance-bearing manifest identifies enough moving-head sequences
   to ground the time-boxed experiment.

This record is not the task's decision memo, does not satisfy any acceptance criterion,
and makes no claim about MH-mining feasibility. The optional task remains incomplete.

The subsequent repository-only audit is recorded in
[P4-T7-repository-preflight.md](P4-T7-repository-preflight.md). It corrects the phantom
vendor-history premise, identifies reusable seams and structural walls, names the exact
five re-entry artifacts, and caps any future admitted offline session at 180 minutes.
That audit also is not task execution, completion, or a feasibility verdict.
