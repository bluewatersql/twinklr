# P2K-T4 — Style fingerprints + propensity refresh

Phase: 2K (M2-K) · Lane: — · Executor: sonnet · Verifier: opus · Depends on: P2K-T2

**Input requirement, not agent taste-making**: which corpus subset(s) constitute
"the author's preferred styles" is owner-supplied information (a short list of style
labels / pack or sequence-file selections), not something this task's agent infers
or invents. If that input is not available when this task runs, the task's tooling
still ships (verified against synthetic groupings) but the actual run against the
author's real preferences waits for the owner to supply the list — do not fabricate
a plausible-looking style grouping to make the task appear complete.

## Objective

Run style-fingerprint extraction over the curated, content-hash-identified corpus
(post P1K-T1) for each of the author's owner-declared preferred style groups, and
rebuild the propensity index with stable (content-hash) identities, verifying both
artifacts are actually consumable by the display planner context that already reads
them — closing out the M2-K exit criteria clauses "propensity/affinity data
populated per element type" and "style fingerprints exist for the author's preferred
styles."

## Evidence & background

- Plan task (`changes/twinklr-reactivation-review/build/plan/05-phase-2k-catalog-growth.md:20`): "Fingerprint extraction
  over the curated corpus for the author's preferred styles; propensity index
  rebuilt with stable identities; both verified consumable by the display planner
  context (the apply edge's data half, ahead of Phase 3's code half)."
- D5, `group_planner` context evidence: the real (indirect) consumer chain P6-F2
  (REVISED) traced is `recipe_synthesizer.py` → `promotion.py` →
  `recipe_catalog.json` → `loader.py::load_fe_artifacts` →
  `agents/sequencer/group_planner/stage.py:30,84,292-314`, which reads
  `fe_bundle.propensity_index`, `.style_fingerprint`, `.vocabulary_extensions` into
  the planner's prompt context (verified: `stage.py:292-294` dumps
  `propensity_index.model_dump(mode="json")` into `result["propensity_hints"]` when
  non-`None`; `:295` similarly reads `style_fingerprint`). This task's job is to
  make sure that pipe actually has real content flowing through it for the author's
  corpus, not to build new plumbing — the plumbing already exists and is verified
  to read these exact fields.
- **Style fingerprint is single-group by construction, not automatically
  per-style**: `write_style_fingerprint(*, output_root, creator_id, phrases, ...)`
  (`feature_engineering/corpus_artifacts.py:572-613`) writes exactly one
  `style_fingerprint.json` per call, keyed by a caller-supplied `creator_id` string
  over whatever `phrases` the caller passes in — `creator_id` is free text with no
  enforced corpus-partition semantics. Producing fingerprints for **multiple**
  preferred styles (plural, per the exit criterion's wording) means calling this
  once per style group with that group's phrase subset and a distinct `creator_id`,
  not a single fingerprint over the whole corpus. Nothing in the current pipeline
  partitions phrases by "style" — that partition is new work this task must add,
  driven by the owner's style-group declaration (see Input requirement above).
- **Propensity identity dependency**: `PropensityMiner.mine()`
  (`feature_engineering/propensity.py:48-112`) itself has no identity fields (it
  operates on `EffectPhrase` objects and emits `EffectModelAffinity`/
  `EffectModelAntiAffinity` rows keyed by `(effect_family, model_type)` pairs, not
  per-instance IDs) — but the **phrases it mines from** trace back to
  `package_id`/`profile_id`/`effect_event_id` identities that P1K-T1 makes
  content-hash-stable. "Propensity index rebuilt with stable identities" means:
  re-run the mining pipeline (T2's hardened tooling) end-to-end post-P1K-T1 so the
  phrases feeding `PropensityMiner` come from deduplicated, content-hash-identified
  corpus rows, not that `PropensityIndex`'s own schema needs an identity field added
  — verify this distinction against P1K-T1's landed spec before assuming otherwise.
- Hand-tuned propensity constants (`_MIN_SUPPORT = 3`,
  `_ANTI_AFFINITY_THRESHOLD = 0.05`, `propensity.py:39,42`) were already reviewed by
  T2's decision-log process — this task does not re-review them, it consumes
  whatever the T2 decision log settled on (or the unchanged defaults if T2 deferred).
- `FEArtifactBundle` (`feature_engineering/loader.py:26-41`) is the typed contract
  both artifacts must round-trip through: `propensity_index: PropensityIndex |
  None`, `style_fingerprint: StyleFingerprint | None` (`loader.py:33-34`).

## Current behavior

- `write_propensity()` (`corpus_artifacts.py:544+`, referenced alongside
  `write_style_fingerprint` at `:572`) and `write_style_fingerprint()` are both
  called once per pipeline run over the full phrase set the run produces — there is
  no per-style-group iteration anywhere in `corpus_artifacts.py` today.
- `stage.py:292-314` already reads whatever `fe_bundle.propensity_index`/
  `.style_fingerprint`/`.vocabulary_extensions` it is given — it has no opinion on
  how many fingerprints exist or how they were partitioned; it is a straight
  passthrough into planner prompt context. This confirms the consumer side needs no
  code change for multiple fingerprints to exist as separate files — it's a data
  question (which fingerprint file does a given planning run load), not a `stage.py`
  code question. `loader.py::load_fe_artifacts` (the function that constructs
  `FEArtifactBundle`) is the actual point deciding which single `style_fingerprint`
  a run loads — check its signature at implementation time; if it currently
  hardcodes a single filename, this task must decide how the planner selects among
  multiple style fingerprints (see Target behavior below) rather than leaving that
  decision implicit.

## Target behavior

1. **Owner style-group declaration.** A small, explicit config (e.g. a JSON/YAML
   list of `{style_name: str, selector: ...}` where `selector` identifies which
   corpus phrases belong to that style — by source pack name, sequence-file
   pattern, or an explicit file list; exact selector shape is this task's design
   call, but it must be inspectable and owner-editable, not inferred from content)
   supplied by the owner before this task's real run. Fail loudly (clear error, not
   a silent skip) if this file is absent when a non-test run is attempted.
2. **Per-style fingerprint extraction.** For each declared style group, filter the
   corpus's `EffectPhrase` set (and the other inputs `write_style_fingerprint`
   needs — `layering_rows`, `color_rows`, `transition_graph`) to that group's
   selector, call `write_style_fingerprint(creator_id=style_name, ...)` with a
   distinct output path per style (e.g.
   `style_fingerprint_<style_name>.json`, not the current single
   `style_fingerprint.json`), and record which styles were successfully fingerprinted
   (enough phrase support to be meaningful — reuse or reference the existing
   `corpus_sequence_count` field on `StyleFingerprint`, `models/style.py:72-74`, to
   flag thin/low-confidence fingerprints rather than silently accepting them).
3. **Propensity rebuild with stable identity.** Re-run T2's hardened mining command
   end-to-end over the full corpus (not per-style — propensity is a whole-corpus
   effect↔model-type index, not a per-style artifact per the plan's wording, which
   only pluralizes "style fingerprints," not "propensity index") with P1K-T1's
   content-hash identity confirmed in effect, producing a fresh `propensity_index`
   free of the duplicate-row inflation P6-M2 described.
4. **Consumability verification.** Confirm `FEArtifactBundle` round-trips both
   artifacts correctly (`propensity_index`/`style_fingerprint` fields populate from
   the newly written files via whatever `load_fe_artifacts` does), and that
   `group_planner/stage.py`'s existing read path
   (`stage.py:292-314`) actually receives non-`None`, non-empty values when given
   this bundle — an integration-level check, not just a schema round-trip, since the
   plan explicitly calls out "verified consumable," implying prior artifacts may
   have existed without ever being checked against the real reader.
5. **Multi-fingerprint selection.** Since the display planner's existing plumbing
   reads a single `style_fingerprint`, decide and document how a planning run picks
   which of the (now multiple) style fingerprints to load for a given show — e.g. a
   `--style <name>` planner input resolving to the matching fingerprint file, or a
   default/no-selection fallback behavior. This is a small, explicit design decision
   this task must make and record (not defer silently) — check whether P1K-T3 or
   P1K-T4 already established a convention for multi-artifact selection in the
   tracked catalog home before inventing a new one.

## Implementation approach

- Files touched: `feature_engineering/corpus_artifacts.py` (per-style-group
  iteration wrapping `write_style_fingerprint`), a new small module for phrase
  filtering by style selector, `feature_engineering/loader.py` (if
  `load_fe_artifacts` needs a style-name parameter for the multi-fingerprint
  selection decision above — re-verify current signature before editing), and
  whichever CLI/script surface T2's hardened mining command uses (extend it with
  the style-fingerprint step rather than building a fully separate entry point).
- Do not touch `PropensityMiner.mine()`'s algorithm — this task's propensity work
  is entirely about re-running the existing miner over cleaned-identity input, not
  changing its logic.
- Do not touch `group_planner/stage.py`'s read logic beyond what's needed for the
  multi-fingerprint selection decision in step 5 — the read path is otherwise
  already correct and verified by P6-F2.

## Acceptance criteria

- [ ] An owner-editable style-group declaration format exists and is documented
  (even if the owner's actual list isn't supplied at task-execution time — the
  format and the fail-loud-when-absent behavior are what's being verified).
- [ ] Given a style-group declaration (owner-supplied or a synthetic test fixture),
  running the tool produces one `style_fingerprint_<name>.json` per declared group,
  each a valid `StyleFingerprint` with a `corpus_sequence_count` reflecting that
  group's actual phrase support (not the whole corpus's count).
- [ ] Thin fingerprints (below some stated, documented minimum support) are flagged
  in the run output, not silently accepted as equal-confidence to well-supported
  ones.
- [ ] A fresh propensity-index rebuild completes over content-hash-identified
  corpus data and shows no duplicate-row inflation (cross-check against T2's
  idempotent-rerun verification).
- [ ] `FEArtifactBundle` round-trips both artifact types from disk with non-`None`
  values.
- [ ] An integration check demonstrates `group_planner/stage.py`'s existing read
  path actually receives and serializes non-empty `propensity_hints` and style-
  fingerprint data from these newly produced artifacts (not just that the schema
  types match).
- [ ] The multi-fingerprint selection mechanism is implemented and documented (even
  minimally) — no silent "always loads whichever file exists" behavior left
  undocumented.

## Tests

- Unit test: style-group phrase filtering against a synthetic phrase set with known
  group memberships, asserting correct partition.
- Unit test: `write_style_fingerprint` called per group produces distinctly named
  output files with the expected `creator_id`/`corpus_sequence_count`.
- Unit test: thin-fingerprint flagging at a stated threshold.
- Integration test: build a small `FEArtifactBundle` from freshly written
  propensity + style-fingerprint artifacts, feed it into
  `SectionPlanningContext`/whatever `stage.py:292-314` actually consumes (re-verify
  the exact call signature at implementation time), and assert the resulting
  planner-context dict contains non-empty `propensity_hints` and style-fingerprint
  data — this is the "verified consumable" acceptance criterion made concrete.

## Verification commands

```bash
uv run mypy packages/twinklr/core/feature_engineering/
uv run ruff check packages/twinklr/core/feature_engineering/
uv run pytest tests/unit/feature_engineering/test_style_fingerprint_groups.py tests/unit/feature_engineering/test_propensity.py -q
uv run pytest tests/integration/feature_engineering/ -k "planner_context or fe_bundle" -q
# LOCAL-ONLY: real corpus + owner-supplied style-group declaration
uv run python scripts/demo_feature_engineering.py --corpus-dir <author-local-corpus> --style-groups <owner-config>
```

## Effort & risk

**M.** Main risk: "the author's preferred styles" has no existing operational
definition anywhere in the codebase — mitigated by treating the selector format and
fail-loud-when-absent behavior as this task's actual deliverable, with the real
owner-driven run happening once that input exists, rather than blocking the task on
an input only the owner can supply. Secondary risk: `load_fe_artifacts`'s current
signature may already assume exactly one style fingerprint file at a fixed path —
re-verify before editing; if so, the multi-fingerprint selection change is a small,
explicit, backward-compatible extension (default to the prior single-file behavior
when no style name is specified), not a breaking change to existing callers.
