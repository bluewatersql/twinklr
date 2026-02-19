# Deferred Task Tracker

## D-001: Template Quality Diagnostics (V1 follow-up)

### Source
- Next-step item `#3`: template quality diagnostics.

### What It Is
- Add a corpus-level diagnostics artifact for mined templates to identify low-value templates before they affect downstream retrieval/ranking.
- Scope of diagnostics:
  - low-support templates (small support_count)
  - high-variance templates (weak internal consistency across phrase members)
  - over-generic templates (high support but low discriminative signal)
  - sequence concentration (templates dominated by one sequence/package)

### Why It Matters
- Prevents noisy templates from degrading retrieval quality and sequence planning recommendations.
- Makes template mining outputs reviewable and actionable for mapping/rules updates.

### Why Deferred (Now)
- Current V1 gating bottleneck was unknown-effect coverage; this is now resolved.
- Core V1 pipeline artifacts are stable and passing strict unknown gates.
- Template diagnostics improve quality and review velocity, but are not required to continue V1 feature engineering development.

### Deferral Decision
- **Status**: Completed
- **Decision date**: 2026-02-19
- **Decision owner**: Feature Engineering

### Trigger To Pull Forward
- Pull into active sprint if any of the following occur:
  - retrieval/ranking quality review reports template noise as a top issue
  - repeated manual mapping changes are driven by template instability
  - template mining output volume grows and manual inspection is no longer practical

### Proposed Implementation Slice
1. Add `template_diagnostics.json` at feature output root.
2. Compute per-template metrics:
   - support_count
   - distinct_pack_count
   - distinct_sequence_count
   - concentration_ratio (max sequence contribution / support_count)
   - optional cohesion proxy from phrase-class distributions.
3. Add flagged lists:
   - `low_support_templates`
   - `high_concentration_templates`
   - `high_variance_templates`
4. Add summary section to demo output/markdown.
5. Add optional quality gate thresholds (warn-only initially).

### Acceptance Criteria
- Artifact exists: `data/features/<run>/template_diagnostics.json`.
- Demo includes a concise diagnostics section.
- Unit tests validate metric computation and flagging behavior.
- No regression in existing quality gates and pipeline outputs.

### Completion Notes
- Implemented in V1 pipeline with artifact output and manifest registration.
- Surfaced in demo console + markdown reporting.
- Covered by unit tests for diagnostics and pipeline integration.

### Risks If Left Deferred Too Long
- Template catalog quality can drift unnoticed.
- Downstream retrieval tuning becomes reactive and slower.
- More manual curation required later.

### Dependencies
- Existing template catalogs (`content_templates.json`, `orchestration_templates.json`).
- Phrase-level artifacts (`effect_phrases`, taxonomy/roles).

---

## D-002: Promote Template Diagnostics Thresholds to Quality Gates

### Source
- Follow-up from D-001 implementation.

### What It Is
- Convert diagnostics thresholds from observability-only signals into enforceable quality gates.
- Add optional fail/warn policy for:
  - `max_low_support_template_ratio`
  - `max_high_concentration_template_ratio`
  - `max_high_variance_template_ratio`
  - `max_over_generic_template_ratio`

### Why Deferred (Now)
- Current V1 completion focus is feature output parity and stability.
- Diagnostics are now visible for manual review; hard gating can create false failures until initial baselines are calibrated on real corpus runs.

### Deferral Decision
- **Status**: Deferred
- **Decision date**: 2026-02-19
- **Decision owner**: Feature Engineering

### Trigger To Pull Forward
- Pull in when either condition is true:
  - repeated diagnostics issues appear across production corpus runs.
  - retrieval quality review attributes ranking noise to flagged template classes.

### Proposed Implementation Slice
1. Extend quality gate options with diagnostics-threshold fields.
2. Add diagnostics-derived checks to `quality_report.json`.
3. Support per-check mode: `warn` or `fail`.
4. Add CLI flags in build/demo scripts for diagnostics thresholds.
5. Add tests for gate pass/fail behavior and deterministic reporting.

### Acceptance Criteria
- Diagnostics gate checks appear in `quality_report.json`.
- Thresholds configurable via pipeline options and CLI flags.
- Warn-only and fail modes both tested.
- Existing V1 quality gates remain backward compatible by default.

### Risks If Left Deferred Too Long
- Template quality regressions remain non-blocking and may accumulate.
- Retrieval tuning remains reactive instead of policy-driven.

### Dependencies
- `template_diagnostics.json` artifact generation (D-001 complete).
- Existing quality gate framework in `datasets/quality.py`.
