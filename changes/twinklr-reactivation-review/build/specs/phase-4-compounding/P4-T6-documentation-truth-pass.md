# P4-T6 — Documentation truth pass

Phase: 4-compounding · Lane: docs (touches `docs/user-guide.md`,
`docs/overview.md`, `docs/pipeline_guide.md`, `docs/developer-guide.md`,
`context/architecture/multi-agent-planning.md`, `context/current-state.md`,
`context/INDEX.md`, `context/product/overview.md`, `scripts/README.md` (new)) ·
Executor: sonnet · Verifier: opus · Depends on: P4-T5 (per
`changes/twinklr-reactivation-review/build/plan/07-phase-4-compounding.md` task table)

## Objective

Bring every user-facing and architecture doc into agreement with the shipped system:
regenerate the user guide's config-knob table from P4-T5's wired/removed ledger (not
from memory or the old table), correct the six-channel claim, remove the stale
LLM-validator architecture claim, remove phantom paths, replace the unsourced "dozens
of hours" marketing claim with measured numbers from the vision-eval harness (D11),
and triage `scripts/` per the phase-7 table (promote/delete/document, no fourth
category).

## Evidence & background

**SF-8** (`findings.md:56`): "Docs describe a different system: six-channel claim
false; removed LLM-validator documented; user-guide knob table unreliable; phantom
paths; 'dozens of hours' claim is unsourced marketing provenance." Sources:
`P7-M2/M3, Stage 2 §1, B7`. Disposition: FIX → RM-5.5.

### Item 1 — User-guide knob table (P7-M2, `verification.md` Phase-7 section)

> "dead-config-class verification (Stage 2 item 5, phases 1+7): `docs/user-guide.md`
> documents as live: `token_budget` (:146, no-op), `judge_agent.model` (:148, never
> wired), `channel_defaults.{shutter,color,gobo}` (:152-154, zero readers),
> `checkpoint` (:157, zero readers), a false resume promise (:296), `logging.level`
> (:121, bypassed), and shutter/color/gobo curve claims (:245, disproved). **Every
> one fails silently. The user guide is not a reliable behavior description —
> confirmed as a CLASS.**"

**This item is downstream of P4-T5, not independent of it.** Do not re-derive which
config members are dead — P4-T5 produces the authoritative wired/removed ledger (its
knob-effect registry). Regenerate the user-guide knob table FROM that ledger: every
field the registry marks `EFFECT_TEST` gets documented as live (with a short note on
its actual observable effect, verified against the test, not assumed); every field
marked `REMOVED` is deleted from the table entirely, not just annotated as
deprecated. If P4-T5 left any member unresolved (shouldn't happen per its acceptance
criteria, but re-verify), do not document it as either live or dead — flag it and
escalate rather than guessing.

The specific line-numbered items above (`:146, :148, :152-154, :157, :296, :121,
:245`) are baseline `aa8d325` citations — re-verify against the current
`docs/user-guide.md`, which will have shifted after P4-T5's changes and possibly
earlier phases' doc touches.

### Item 2 — Six-channel claim (P4-F16 family, cross-cited in `moving-heads-rendering.md`:401)

> "Six channels choreographed" (`docs/overview.md:24`) — "**Refuted.** Three
> channels (pan, tilt, dimmer). 0/37 templates reference color/gobo/shutter
> (P4-F16)."

**Re-verify against current state before correcting**: by Phase 4, earlier phases
(1P/2P/3) may have landed color/gobo/shutter widening (the `07-phase-4-compounding.md`
overview lists "Widened channel live" as a Phase 2P exit criterion). If the channel
count is now genuinely six (or some other number), correct `docs/overview.md:24` to
the TRUE current count with evidence (re-run the same check the finding used: grep
which channels the 37 MH templates actually reference). If it is still three,
correct the claim to three and note the color/gobo/shutter libraries' status
(wired, or still dormant pending the P4-T3 CONDITIONAL decision on those libraries —
cross-reference P4-T3's Group G item 14 CONDITIONAL row if it's still open).

### Item 3 — Removed LLM-validator claim (discovery §4, `llm-agents-and-planning.md:795-798`, `interfaces-and-engineering.md:547,591`)

> "`context/architecture/multi-agent-planning.md` documents a planner → heuristic →
> **LLM validator** → judge loop. The LLM-validator role does not exist in code
> (confirmed; also flagged in discovery §4). `context/current-state.md:23` repeats
> it." Also `context/INDEX.md` "lists it first under 'Start here'" per P7-F16 —
> meaning this stale claim is not buried, it's the entry point.

Correct both `context/architecture/multi-agent-planning.md` and
`context/current-state.md:23` to describe the actual loop (planner → heuristic
validator → judge — no separate LLM-validator stage) in the SAME edit, since
`verification.md` explicitly notes these are "the same claim" duplicated across two
documents and must not be fixed in only one. `context/INDEX.md`'s "Start here"
pointer does not itself need factual correction (it's a navigation link) but confirm
it now points to the corrected document.

### Item 4 — Phantom paths (P7-F2, `interfaces-and-engineering.md:577,542`)

> "`docs/pipeline_guide.md`'s 'recommended' Quick Start references `scripts/build/`"
> — `pipeline_guide.md:31-36,884,894` (10 refs total). "true 'never existed' only for
> 6/10 refs, the other 4 are stale-after-deletion (`scripts/build/` was real, deleted
> 2026-02-24, `82aaf38`)." **Verifier's remedy, which this task must follow
> verbatim, not the original "rewrite toward a working entrypoint" instinct**: "mark
> the guide as describing an ABANDON-candidate subsystem (corpus/FE, per Stage 2)
> pending its retire/restore decision — not a rewrite toward a currently-working
> entrypoint." Do not invent a replacement `scripts/build/` workflow to make the
> guide "true" — that would be scope creep into feature work. The correct fix is
> honest labeling: this guide describes a subsystem whose CLI entrypoint was
> deleted; state that plainly, point at the still-live pieces (`scripts/demo_sequencer_pipeline.py`
> per the scripts triage table, Item 5 below), and stop there.

### Item 5 — scripts/ triage (P7-M3 + the phase-7 triage table,
`interfaces-and-engineering.md:258-276,594`)

> P7-M3: "`docs/developer-guide.md:348` 'Key Scripts' table has 2 of 5 rows pointing
> at nonexistent files (`build_pipeline.py`, `show_coverage_by_component.py`)."

Full triage table (verified categories, from `interfaces-and-engineering.md:262-270`
— re-verify file existence against current tree before acting, scripts may have
moved since baseline):

| Category | Files | Action for this task |
|---|---|---|
| Promoted/real tool | `scripts/validation/validate_artifacts.py`, `validate_agent_artifacts.py` | Document accurately in `developer-guide.md`; note they are "not wired into `Makefile` or CI at all" as a KNOWN gap, not a doc error — wiring them is out of this task's scope (it's an engineering task, not a docs task) unless another Phase-4 task already did it; re-verify |
| Wired, working | `scripts/test_audio_pipeline.py` | Document as-is; note the pytest-name-but-not-pytest ambiguity honestly (P7-F10 family) |
| Misleadingly named, uncollected | `scripts/validation/test_prompt_validation.py`, `test_schema_validation.py` | Document with the naming caveat explicit: "despite the name, `pytest` does not collect these" |
| Demo/exploration, load-bearing | `scripts/demo_sequencer_pipeline.py` | Document as "the only caller anywhere of `build_display_pipeline`" — the canonical way to exercise the display pipeline outside the CLI; give it the dedicated "how to run this" callout the finding says it's currently missing |
| Demo/exploration, corpus-tooling | `demo_display_renderer.py`, `demo_eval_report.py`, `demo_feature_engineering.py`, `demo_moving_heads_pipeline.py`, `demo_profiling.py`, `demo_recipe_builder.py`, `demo_recipe_pipeline.py` | List in a new `scripts/README.md` (see below) so they're discoverable without directory-browsing |
| Analysis (offline, data-dependent) | `cross_lane_profile_analysis.py`, `normalize_unknown_effects.py`, `validate_rules_against_profiles.py` | Document with the data-dependency caveat: requires gitignored `data/features/...` corpus artifacts, not runnable from a clean checkout |
| Template/corpus tooling | `enrich_builtin_templates.py`, `evaluate_recipe_dictionary.py`, `query_template_retrieval.py`, `cleanup_display_templates.py`, `validate_fe_output.py` | Same data-dependency caveat; flag `query_template_retrieval.py` as "zero references anywhere outside itself — likely dead" rather than documenting it as a working tool |
| Orphaned, unrelated to product | `utils/video_demo.py` | **Promote/delete decision needed** — this is OpenAI video-generation experimental code, "zero references anywhere in application code, tests, docs, or Makefile," unrelated to lighting choreography. This task's docs pass should NOT silently document it as legitimate; either flag it for deletion (file a note, since deleting it is arguably P4-T3-adjacent dead-code work now discovered late — coordinate rather than deleting unilaterally from a docs task) or, if kept, add the one-line docstring explaining why it's there, per the finding's own suggestion |
| Docs-only | `scripts/docs/feature_engineering.md`, `scripts/validation/README.md` | No action needed |

**Fix `docs/developer-guide.md:348`'s two nonexistent-file rows**
(`build_pipeline.py`, `show_coverage_by_component.py`) directly: `build_pipeline.py`
was in the deleted `scripts/build/` (see Item 4 — same ABANDON-candidate framing
applies); `show_coverage_by_component.py` "existed and was deleted 2026-01-30
(`c67bbdd`), restorable via `git show c67bbdd^:scripts/show_coverage_by_component.py`"
(P7-F5) — state in the table that this script is restorable-but-not-restored, not
that it's a working entrypoint.

**New `scripts/README.md`**: create one indexing all ~30 files by the categories
above — the finding notes "no top-level `scripts/README.md` indexes any of this...
the remaining 19 [of 30 Python files] have no discoverability aid beyond in-file
docstrings."

### Item 6 — "Dozens of hours" claim (product-and-approach.md:66-68,
`findings.md` SF-8)

> "The 'replaces dozens of hours' claim traces commit-by-commit to a deleted blog
> draft's literal 'Opening Hook' (2026-02-12), then README (39 minutes later), then
> docs (2026-03-08), then canonical context (2026-08-13) — never gaining a source.
> It must not be treated as an input to Stage 8."

Find every occurrence of this claim (grep `docs/`, `README.md`, `context/product/overview.md`
per the citation "`context/product/overview.md` three-scope + 'dozens of hours'
claims" at `product-and-approach.md:223`) and replace it with **measured numbers
from the D11 vision-eval harness** — per the plan's exit criterion: "'dozens of
hours' replaced by measured numbers from the eval harness." This requires the eval
harness (built in Phase 2P/M2 per `reactivation-proposal.md` §4) to have actually run
and produced real cost/time numbers by the time this task executes — if it has not
yet run enough to produce a defensible number, **do not invent a replacement
number**; instead state the claim is retracted pending measurement, with a pointer to
wherever the eval harness's output will land. An unsourced number replaced by another
unsourced number is not a fix.

## Current behavior

`docs/user-guide.md`'s config-knob table documents multiple dead fields as live
(Item 1). `docs/overview.md:24` claims six choreographed channels against a verified
three (pending Item 2's re-verification). `context/architecture/multi-agent-planning.md`
and `context/current-state.md:23` both describe a planner→heuristic→LLM-validator→judge
loop that doesn't exist in code, and `context/INDEX.md` surfaces this as the first
"Start here" document. `docs/pipeline_guide.md` recommends a deleted `scripts/build/`
workflow as the "recommended" Quick Start. `docs/developer-guide.md:348`'s Key
Scripts table has 2 of 5 rows pointing at files that don't exist. No
`scripts/README.md` exists. An unsourced "dozens of hours" marketing claim appears in
multiple docs tracing to a deleted blog draft with no underlying measurement.

## Target behavior

Every item above corrected per its specific remedy (regenerate from P4-T5's ledger,
not from memory; honest ABANDON-candidate labeling rather than invented fixes for
Item 4; measured numbers or explicit retraction for Item 6). No doc claims a
behavior the code doesn't have; no doc omits a script or config knob that a
developer/user would reasonably need to find.

**Non-goals:** wiring `validate_artifacts.py`/`validate_agent_artifacts.py` into
`Makefile`/CI (an engineering task, not a docs task — document the gap honestly
instead). Rewriting `docs/pipeline_guide.md` toward a new working
`scripts/build/`-equivalent workflow (explicitly rejected by the phase-7 verifier's
remedy). Deleting `utils/video_demo.py` unilaterally from a docs-scoped task —
flag it, don't remove code here.

## Implementation approach

Do Item 1 last (it depends on P4-T5's completed ledger being final) but everything
else can proceed in parallel. For each doc file touched, cite the specific finding
ID in the commit/PR description so the verifier can trace every doc change back to
verified evidence rather than the executor's own judgment about what's "probably
also stale" — this task corrects VERIFIED claims, it does not go hunting for
additional unverified staleness (that's a different, open-ended task).

Re-verify every line-numbered citation above against the current tree — several of
these docs may have already shifted from baseline `aa8d325` due to earlier phases'
work (e.g., Phase 2P's model retarget touches `judge_agent.model` documentation;
Phase 1P/3 may have touched user-guide sections describing the render path).

## Acceptance criteria

- `docs/user-guide.md`'s config-knob table matches P4-T5's wired/removed ledger
  exactly — every documented field is provably live (per that ledger's effect test)
  or absent from the table.
- `docs/overview.md:24`'s channel-count claim matches a fresh grep-verified count of
  what the 37 MH templates actually reference, with the check's method stated
  inline or in a linked doc (so it's re-verifiable, not just asserted).
- `context/architecture/multi-agent-planning.md` and `context/current-state.md:23`
  both describe the loop without a separate LLM-validator stage, corrected in the
  same commit.
- `docs/pipeline_guide.md`'s `scripts/build/` references are relabeled as describing
  an ABANDON-candidate subsystem with the deletion history noted (commit `82aaf38`,
  2026-02-24) — not rewritten toward a fictitious working entrypoint.
- `docs/developer-guide.md:348`'s Key Scripts table has zero rows pointing at
  nonexistent files; `show_coverage_by_component.py` is noted as
  restorable-not-restored with its restore command.
- `scripts/README.md` exists and indexes all ~30 files per the triage table's
  categories.
- Every occurrence of the "dozens of hours" claim is either replaced with a cited,
  measured number from the D11 harness or explicitly retracted with a pointer to
  pending measurement — zero occurrences of the original unsourced claim remain.

## Tests

Documentation changes are not unit-testable in the traditional sense. Verification
is evidence-tracing: the verifier confirms each changed doc claim against the cited
finding/ledger, not against a test suite. If the executor adds any doc-linting
tooling (e.g., a script that checks `docs/user-guide.md`'s knob table against
P4-T5's registry programmatically, closing the loop so this doesn't drift again),
that is a welcome bonus but not a required deliverable of this task — do not treat
it as blocking if time-boxed effort runs out; note it as a follow-up instead.

## Verification commands

```bash
git grep -in "dozens of hours"                    # expect zero hits after this task
git grep -in "six channel"  docs/                  # expect zero, or a corrected true count
git grep -in "LLM validator" context/              # expect zero
git grep -n "scripts/build" docs/pipeline_guide.md # expect ABANDON-candidate framing, not "recommended"
ls scripts/README.md                               # expect present
uv run ruff check .    # docs changes shouldn't touch code, but confirm no incidental breakage
```

No LOCAL-ONLY steps.

## Effort & risk

**S/M.** Main risk: Item 1 (user-guide regeneration) is entirely dependent on P4-T5
landing first and being complete — if P4-T5's ledger has gaps (a config field it
missed), this task will faithfully propagate that gap into the docs. Mitigation:
confirm P4-T5's acceptance criteria (the generated knob-inventory test passing) hold
before starting Item 1, and treat any inconsistency discovered while writing docs as
a signal to go back to P4-T5's ledger, not to paper over it with prose.
