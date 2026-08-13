# P1K-T2 — Wire the active-learning loop

⚖ Design-bearing: fixes an ambiguous internal contract (`applier.py`'s
`candidate_id`-keying) and sets `enable_active_learning`'s default explicitly.
Not owner-decision-bearing (no product tradeoff exposed to the project owner) —
opus executes and verifies because the contract fix is subtle enough to get
wrong silently.

Phase: 1K · Lane: AL · Executor: opus · Verifier: opus · Depends on: P1K-T1

## Objective

Connect the built-but-orphaned active-learning chain — `UncertaintySampler`
(already wired, default-off) → `ReviewBatchBuilder` → a human-or-LLM oracle →
`CorrectionApplier` → a persisted correction store that `TaxonomyClassifier`
reads on its *next* run — so that a human (or LLM) taxonomy correction
demonstrably changes future mining output. Today only the sampler runs; nothing
downstream of it has a caller, and the one caller-contract question that blocks
wiring `CorrectionApplier` in (how `taxonomy_rules` is keyed) is answered
ambiguously in the module's own code comments. This task resolves that
ambiguity explicitly and builds the missing round-trip.

## Evidence & background

Finding, corpus-intelligence review ("active_learning/ is more thoroughly
orphaned than discovery stated"): `TaxonomyReviewOracle` and `CorrectionApplier`
have **zero non-test callers anywhere in the repository**, including from the
mining pipeline itself — `corpus_artifacts.py:221-231` instantiates only
`UncertaintySampler` even when `enable_active_learning=True`; the flag defaults
`False` (`feature_engineering/config.py:132`); `active_learning/__init__.py`
declares `__all__ = []` (P6-M4, LOW — an explicit "not meant to be imported from
outside" signal). Full text:
`changes/twinklr-reactivation-review/reviews/phases/corpus-intelligence.md`
("active_learning/ is more thoroughly orphaned..." + P6-M4);
`reactivation-proposal.md` §2.2 item 3 ("Labels: learned taxonomy trained on its
own rule engine (circular) → wire the built-but-orphaned active-learning
correction loop").

**Current wiring** (`corpus_artifacts.py:221-243`, baseline `aa8d325`):

```python
if o.enable_active_learning and phrases and taxonomy_rows:
    sampler = UncertaintySampler(UncertaintySamplerOptions())
    candidates = sampler.sample(phrases, taxonomy_rows)
    if candidates:
        batch_data = {"schema_version": "1.0.0", "total_candidates": len(candidates),
                       "candidates": [c.model_dump(mode="json") for c in candidates]}
        m["review_batch"] = str(w.write_review_batch(output_root, batch_data))
```

`w.write_review_batch()` (`feature_engineering/datasets/writer.py:265-...`)
writes a raw dict of candidates only — never a real `ReviewBatch` (with
`ReviewItem`s, context phrases, resolver suggestions). `ReviewBatchBuilder`,
`TaxonomyReviewOracle`, and `CorrectionApplier` are never invoked from this or
any other production path.

**The applier.py ambiguity** (`active_learning/applier.py:107-131`, verbatim
comments left in the source):

```python
# Try to find by matching original values if candidate_id not a key.
# taxonomy_rules is keyed by effect_type; we need to resolve it.
# Since TaxonomyCorrectionResult doesn't carry effect_type directly,
# we match by original_family/motion in any entry whose values match,
# but that is ambiguous.  The applier contract expects the caller to
# key taxonomy_rules by effect_type AND the candidate_id equals the
# effect_type OR the caller maps appropriately.
# Per the model: CorrectionRecord has effect_type; we emit it as
# candidate_id since that is all we have from TaxonomyCorrectionResult.
```

The code that follows this comment actually reads/writes
`taxonomy_rules[result.candidate_id]` and sets
`CorrectionRecord(effect_type=result.candidate_id, ...)` — i.e. it keys by
`candidate_id` in practice, while the docstring/comment claim it should be keyed
by `effect_type`, and `CorrectionRecord.effect_type` is populated with the wrong
value (a candidate id, not an effect type) because
`TaxonomyCorrectionResult` has no `effect_type` field to draw the real value
from. This is the exact ambiguity this spec resolves (below).

`UncertaintyCandidate.candidate_id` is deterministic today:
`hashlib.sha1(normalized_key.encode()).hexdigest()[:16]` where
`normalized_key = f"{effect_type}::{param_signature}"` (`sampler.py:63,103`) —
this is stable across runs for the same `(effect_type, param_signature)` pair,
which is exactly the granularity a taxonomy correction should target (it is
*more specific* than `effect_type` alone, since one `effect_type` can have
multiple `param_signature` variants with different correct labels).

`TaxonomyClassifier` (`taxonomy/classifier.py`) reads a weighted-rules JSON
config (`taxonomy/config/effect_function_v2.json` by default,
`_DEFAULT_CONFIG`, `classifier.py:17`), structured as
`{"labels": {<label>: {"base": float, "min_confidence": float, "rules": [{"id": str, "when": dict, "weight": float}]}}}`.
`_matches()` (`classifier.py:122-155`) evaluates `when` as an exact/range match
against **any** attribute readable via `getattr(phrase, key)` — including
`param_signature` and `effect_type`, both real `EffectPhrase` fields consumed
elsewhere in this same package. `TaxonomyClassifierOptions.rules_path`
(`classifier.py:24`) already lets a caller point at an alternate rules file, and
`component_factory.py:104-105` already threads
`self._options.taxonomy_rules_path` through — this is the existing extension
point this task builds on, it does not need a new one invented.

**Depends on P1K-T1**: `UncertaintyCandidate.candidate_id` and
`sample_phrase_ids` reference `EffectPhrase`/`phrase_id`/`effect_event_id`
values; the plan's Lane AL ordering note ("T2 ... after T1 (stable IDs)")
exists so correction records reference stable phrase/event identity rather than
per-run-random ones. Re-verify T1 has landed before starting T2.

## Current behavior

`UncertaintySampler.sample()` runs (when `enable_active_learning=True`,
currently never true by default) and writes a raw candidate dump to
`review_batch.json`. Nothing reads that file back. `ReviewBatchBuilder`,
`TaxonomyReviewOracle`, `CorrectionApplier` are fully built, individually unit
tested, and never invoked outside their own tests. `taxonomy/config/effect_function_v2.json`
never changes as a result of any review, so `TaxonomyClassifier`'s next run
always reproduces the same rule-based output it always has — the
"learned taxonomy trained on its own rule engine" circularity the review flags.

## Target behavior

1. **Resolve the keying contract** (fixes the `applier.py` ambiguity):
   - Add `effect_type: str` to `TaxonomyCorrectionResult`
     (`active_learning/models.py`), populated from `ReviewItem.candidate.effect_type`
     wherever a `TaxonomyCorrectionResult` is constructed (`oracle.py:144-153`'s
     `_parse_llm_response`, and any new human-review parsing path — see below).
   - `CorrectionApplier.apply()`'s `taxonomy_rules` parameter is keyed and
     documented as keyed by **`candidate_id`** (the sha1 hash), not
     `effect_type` — update the docstring and rename the parameter to
     `taxonomy_overrides: dict[str, dict[str, str]]` to stop implying an
     `effect_type` key. `CorrectionRecord.effect_type` is now populated from
     the corrected `TaxonomyCorrectionResult.effect_type` field (the real
     value), not aliased from `candidate_id`. Remove the resolved ambiguity
     comment block; replace with a short docstring stating the contract
     plainly.
   - Delete the now-dead "Try to find by matching original values..." branch —
     it is unreachable once the key is unambiguously `candidate_id`.

2. **Default oracle mode: human-reviewed** (per plan note — "default to
   human-reviewed batches — this loop exists to inject non-model truth"). Both
   `TaxonomyReviewOracle` (LLM) and a plain human-edited JSON file produce the
   *same* `TaxonomyCorrectionResult` shape, so either can feed
   `CorrectionApplier` unchanged:
   - `ReviewBatchBuilder().build(candidates, phrases, resolver=...)` produces a
     full `ReviewBatch` (not a raw dict); write it via
     `w.write_review_batch(output_root, batch.model_dump(mode="json"))`
     (`write_review_batch`'s existing signature accepts any JSON-serializable
     dict — no signature change needed, only the payload construction changes).
   - A human reviews `review_batch.json` and produces a sibling
     `taxonomy_corrections.json` — a JSON array of objects matching
     `TaxonomyCorrectionResult`'s field set (`candidate_id`, `effect_type`,
     `original_family`, `original_motion`, `corrected_family`,
     `corrected_motion`, `correction_confidence`, `rationale`, `approved`).
     This is the same schema an LLM oracle run via `TaxonomyReviewOracle.review()`
     already produces — no format fork between the two paths.
   - New orchestration function `active_learning/applier.py::apply_corrections_file`
     (or a small new module `active_learning/pipeline.py` — executor's choice,
     but it must live under `feature_engineering/active_learning/` and be
     exported from `active_learning/__init__.py`'s `__all__`, replacing the
     current `__all__ = []`): loads `taxonomy_corrections.json` if present,
     parses it into `tuple[TaxonomyCorrectionResult, ...]`, calls
     `CorrectionApplier().apply(corrections, taxonomy_overrides)`, and returns
     the `CorrectionReport`.

3. **Persist corrections so the next run's `TaxonomyClassifier` actually
   changes** (closes the "labels" edge — §2.2 item 3):
   - Approved corrections are written to a new git-tracked file
     `feature_engineering/taxonomy/config/corrections.json`, in the **same
     schema** as `effect_function_v2.json` (labels → rules → when/weight) —
     each approved correction becomes one additive rule per corrected label:
     `{"id": "correction:{candidate_id}", "when": {"effect_type": <exact>, "param_signature": <exact>}, "weight": 1.0}`
     appended under the corrected label's `rules` list (creating the label
     entry with `base: 0.0, min_confidence: 0.0, rules: []` if it doesn't
     already exist in the corrections file). This is additive-only — never
     rewrite or delete existing rules in `corrections.json`, and never write
     into `effect_function_v2.json` itself (that file stays the deterministic,
     git-reviewable rule baseline; corrections are a separate, explicitly
     human-curated layer on top of it, itself git-tracked and reviewable via
     normal PR diff).
   - `TaxonomyClassifierOptions` gains a new field `corrections_path: Path | None = None`.
     `TaxonomyClassifier._load_config()` loads the base config (`rules_path`)
     and, if `corrections_path` is set and the file exists, deep-merges its
     `labels[*].rules` lists into the base config's matching labels (append,
     not replace) before building `self._labels`. `component_factory.py`
     passes `self._options.taxonomy_rules_path` (existing) and a new
     `self._options.taxonomy_corrections_path` (new, defaulting to
     `feature_engineering/taxonomy/config/corrections.json` when that file
     exists, else `None`) into `TaxonomyClassifierOptions`.
   - Because a `when` clause matching `effect_type` + `param_signature` exactly
     is the highest-specificity match `_matches()` supports (it does not
     downweight for specificity — any hit at or above `min_confidence` counts),
     a `weight: 1.0` correction rule with `min_confidence: 0.0` on its label
     guarantees that label scores highest for that exact
     `(effect_type, param_signature)` pair on the next classification run,
     without needing to touch `_matches()` or the scoring loop at all.

4. **`enable_active_learning` default stays `False`, decision made explicit**:
   this task does not flip the default. Document in
   `feature_engineering/config.py`'s docstring for `enable_active_learning`
   *why* it stays off by default: it produces a review artifact
   (`review_batch.json`) that requires a human (or a separate, explicit oracle
   invocation) to act on before anything changes — it is a human-in-the-loop
   step, not a fully-automated pipeline stage, so it must not silently activate
   on every corpus run.

**Non-goals**: no change to `UncertaintySampler`'s sampling logic; no change to
`_matches()`/the deterministic scoring loop in `classifier.py` beyond loading
an additional, additive rules source; no automatic LLM-oracle invocation by
default (human-reviewed is the default path — an LLM-oracle run is an explicit,
separately-invoked alternative producing the same `taxonomy_corrections.json`
shape, wireable later without further design work here).

## Implementation approach

Files:

- `packages/twinklr/core/feature_engineering/active_learning/models.py` — add
  `effect_type: str` to `TaxonomyCorrectionResult`.
- `packages/twinklr/core/feature_engineering/active_learning/oracle.py` —
  populate the new field in `_parse_llm_response`'s success and fallback
  branches from `item.candidate.effect_type`.
- `packages/twinklr/core/feature_engineering/active_learning/applier.py` —
  rewrite the keying contract as specified; delete the dead
  fallback-matching branch; update docstrings.
- `packages/twinklr/core/feature_engineering/active_learning/__init__.py` —
  export the new orchestration entry point(s); replace `__all__ = []`.
- New: `packages/twinklr/core/feature_engineering/active_learning/pipeline.py`
  (or extend `applier.py`) — `apply_corrections_file()` orchestration function
  described above.
- `packages/twinklr/core/feature_engineering/taxonomy/classifier.py` —
  `TaxonomyClassifierOptions.corrections_path`; merge logic in `_load_config`.
- `packages/twinklr/core/feature_engineering/component_factory.py:104-105` —
  thread the new corrections path through.
- `packages/twinklr/core/feature_engineering/config.py` — docstring update on
  `enable_active_learning`; no default-value change.
- `packages/twinklr/core/feature_engineering/corpus_artifacts.py:221-243` —
  replace the sampler-only block with sample → build (full `ReviewBatch`) →
  write; wire the corrections-file check + apply + persist step described in
  point 2/3 above, gated the same as today (`enable_active_learning`).
- New git-tracked file (created empty/seeded with `{"schema_version": "1.0.0", "labels": {}}`):
  `packages/twinklr/core/feature_engineering/taxonomy/config/corrections.json`.

Sequencing constraint: depends on P1K-T1 landing first (stable phrase/event
identity feeding `UncertaintyCandidate.sample_phrase_ids`).

## Acceptance criteria

- `TaxonomyCorrectionResult` carries a real `effect_type` field, populated
  correctly by the oracle path.
- `CorrectionApplier.apply()`'s contract (parameter name, docstring, and
  behavior) is unambiguously keyed by `candidate_id`; the dead fallback-matching
  branch and its explanatory comment block are removed.
- `active_learning/__init__.py` exports at least one real orchestration entry
  point; `__all__` is no longer `[]`.
- Running the mining pipeline with `enable_active_learning=True` over a corpus
  with uncertain phrases, then supplying a hand-written
  `taxonomy_corrections.json` with one `approved=True` correction, then
  re-running the pipeline: the correction is merged into
  `taxonomy/config/corrections.json` as an additive rule, and a **fresh**
  `TaxonomyClassifier` instance constructed with the default config +
  corrections path classifies the corrected `(effect_type, param_signature)`
  pair with the corrected label — demonstrated end-to-end in a test.
- `effect_function_v2.json` itself is never written to by this loop — only
  `corrections.json` is.
- `enable_active_learning` still defaults to `False`; its docstring explains
  why.

## Tests

TDD — write the round-trip test first against current (failing) behavior:

- `tests/unit/feature_engineering/active_learning/test_applier.py`: rewrite/add
  cases asserting `taxonomy_overrides` keyed by `candidate_id`, and that
  `CorrectionRecord.effect_type` reflects the real effect type, not the
  candidate id.
- `tests/unit/feature_engineering/active_learning/test_pipeline.py` (new):
  `test_apply_corrections_file_merges_into_corrections_json` — given a fake
  `taxonomy_corrections.json` with one approved correction, assert the merged
  `corrections.json` gains exactly one new rule under the corrected label, and
  that a second run with the same correction does not duplicate the rule
  (idempotent merge, keyed by the `"correction:{candidate_id}"` rule id).
- `tests/unit/feature_engineering/taxonomy/test_classifier.py`: add
  `test_corrections_path_overrides_next_classification` — construct a
  `TaxonomyClassifier` with `rules_path=<base>` and
  `corrections_path=<corrections with one rule for a known phrase>`, classify a
  phrase matching that correction's `when` clause, assert the corrected label
  wins.
- `tests/unit/feature_engineering/test_corpus_artifacts.py` (or wherever
  `run_pipeline`/its active-learning branch is tested): end-to-end test with
  `enable_active_learning=True`, asserting the full sample→build→(no
  corrections file yet)→write behavior on first run, and
  sample→build→(corrections file present)→apply→persist behavior on a second
  run.

## Verification commands

```bash
uv run pytest tests/unit/feature_engineering/active_learning/ -q
uv run pytest tests/unit/feature_engineering/taxonomy/test_classifier.py -q
uv run pytest tests/unit/feature_engineering/test_corpus_artifacts.py -q
uv run ruff check packages/twinklr/core/feature_engineering/active_learning packages/twinklr/core/feature_engineering/taxonomy
uv run mypy packages/twinklr/core/feature_engineering/active_learning packages/twinklr/core/feature_engineering/taxonomy
```

No LOCAL-ONLY / paid-API steps — the default path is human-reviewed (no LLM
call required to demonstrate the loop); an LLM-oracle exercise is optional and
out of this task's required test budget.

## Effort & risk

**L.** This is the most design-bearing task in the phase — it resolves a
real ambiguity in existing code and introduces a new persisted-corrections
format that a later classifier load must merge correctly. Main risk: getting
the `corrections.json` merge semantics wrong in a way that silently
double-applies or loses corrections across repeated runs — mitigated by the
dedicated idempotent-merge test above (rule ids keyed by `candidate_id`, so a
re-applied identical correction is a no-op, not a duplicate). Secondary risk:
conflating this task's "human-reviewed by default" scope creep into building a
full review UI — out of scope; the human step is "hand-edit a JSON file," no
tooling beyond that is required here.
