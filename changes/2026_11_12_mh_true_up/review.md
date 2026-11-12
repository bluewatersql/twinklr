---
type: review
status: complete
area: reference
created: 2026-11-12
updated: 2026-11-12
---

# Independent moving-head research review

Verdict: **approved** as a research deliverable. No material findings requiring changes.
This is independent document/source review, not owner approval of a roadmap, altered
render semantics, hardware behavior, or aesthetic quality.

## Scope

Read the repository guardrails, research brief, independent review workflow, context
index/current state, and active-change index. Reviewed the actual report and evidence
record, including the proposed P0–P5 plan, transfer matrices, baseline limitations,
competitor analysis, provenance, and explicitly excluded experiments. The author is
finalizing the handoff separately; its temporary absence was disclosed before review.

## Evidence checked

- Independently read the pinned scratch xLights generator/header, UI insertion path,
  native pattern/DMX renderer, and panel linking implementation. Checked classification
  precedence, fixed pan/tilt vocabulary, peak-only behavior, section-relative burst
  schedule, all-head ordering with subset filtering, limited slew-based trimming,
  slot addressing, deletion/locked-effect behavior, serialization, and pattern math.
- Re-ran the existing synthetic probe executable: exit 0 with the reported 24/4/0,
  24/4/0, and 44/36/8 counts; subset parity passed; insufficient slow-fixture travel
  remained detectable. This review did not rebuild the executable or run the xLights GUI.
- Independently compared the three scratch source/release files: exact byte equality.
  Recomputed generator, dialog, renderer, and header SHA-256 values; they matched the
  evidence table.
- Inspected Twinklr builder, movement/dimmer/wheel handlers, step compiler, and builtin
  registry. The consequential claims about absent coarse/fine realization, ineffective
  passed movement intensity, unbounded calibrated excursion, shutter channel ceiling,
  average-bar internal dimmer phase, and the one-shot dimmer wrap exception agree with
  implementation. Counted 37 builtin imports. No moving-head source diff exists between
  audited commit 2d1af61 and observed HEAD 9c55c2e; the later changes are golden artifacts.
- Checked all 32 named local source targets; all exist. Checked reference definitions,
  including XWiki. Public source pins and audit date are explicit. Reopened official
  xLights release, SoundSwitch product/phrase documentation, Titan 19 cue-list options,
  Lightkey specifications, and pinned QLC+ source as targeted external spot checks.
  Their reviewed claims are supported; commercial internals are not represented as
  inspected source.

## Assessment

The deliverable covers the requested xLights investigation, transferable mechanisms,
other DMX/moving-head projects and products, differentiator hypotheses, and an integrated
prioritized phased plan. It identifies existing Twinklr facilities before proposing
extensions, keeps numeric precision outside LLM control, preserves accepted behavior
through explicit migration/versioning, and distinguishes source-function evidence from
frame output, physical movement, taste, and measured authoring benefit. The proposed
phases have concrete dependencies and exit criteria without treating pending owner
experiments as established results.

No application code or public contract changes are part of this deliverable. Full
make validate was not run by this reviewer; its omission is explicitly disclosed in
the report/evidence. External checks were targeted, not a complete independent crawl
of every linked manual. No live providers, owner-local media/layout/corpus data,
running xLights show, repository edits, or Git mutations were used in this review.
