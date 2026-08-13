# Phase 1K — Knowledge Edges (Track K / M1-K)

_Goal: the learning loop's structural edges work — corpus accumulates idempotently,
human corrections flow, the catalog becomes durable project knowledge. Runs fully
parallel with Phase 1P (disjoint files: `feature_engineering/`, `feature_store/`,
`profiling/`, `recipe_builder/`, `data-catalog`). Proposal M1-K; edges §2.2._

**Exit criteria:** re-ingesting the same archive is a no-op (same primary keys); a
human taxonomy correction demonstrably changes the next mining run's labels; a
versioned seed catalog exists in git; recipe-generation LLM calls run inside the
provider framework.

## Lanes

- **Lane ID (identity)**: T1 (feature_store + profiling).
- **Lane AL (labels)**: T2 (active_learning + taxonomy) — after T1 (stable IDs).
- **Lane CAT (catalog)**: T3 → T4 (recipe_builder, templates store, git data home).
- **Lane FW (framework)**: T5 (normalization/generation LLM plumbing) — independent.

## Tasks

| ID | Title | What (summary) | Evidence | Deps | Executor | Verifier |
|---|---|---|---|---|---|---|
| P1K-T1 | Content-hash corpus identity | Replace uuid4 identities with content-hash keys everywhere the hash is already computed-and-discarded (`package_id`←zip_sha256, `file_id`←file sha, deterministic `effect_event_id`/`corpus_id`); migration note for existing local stores (recreate — no migration machinery exists by design, version gate raises). Upsert semantics become genuinely idempotent. | P6-M2, feature_store schema evidence | — | opus | opus |
| P1K-T2 | Wire the active-learning loop | Connect the built-but-orphaned chain: `UncertaintySampler` (already wired, default-off) → `ReviewBatchBuilder` → human/LLM oracle review → `CorrectionApplier` → corrections persist into the taxonomy config consumed by the next run (today corrections have no path back; the applier's ambiguity comments get resolved by an actual caller contract). Turn `enable_active_learning` default decision explicit. This is what breaks the weak-supervision circularity over time. | P6 edges, applier.py ambiguity notes | P1K-T1 | opus | opus |
| P1K-T3 | Catalog in git (D9) | Create the tracked catalog home (coordinate with P0-T2's test fixtures — same data, one home): seed content = existing builtin display recipes + curated first mining pass over the author's local corpus; `TemplateStore` reads tracked-catalog-then-local-extensions; provenance (`source: builtin/mined/curated/generated`) preserved; document the don't-redistribute-vendor-content courtesy rule in the catalog README. | D9, P5 store evidence, RecipeProvenance | P1K-T1 | sonnet | opus |
| P1K-T4 | recipe_builder session hardening | Make the curation workflow a first-class command (it's a demo script today), running against the tracked catalog; verify staged-only/promotion-gate behavior end-to-end with the new home; fix the corpus_artifacts silent parquet-error swallow and config default-path validation. | P6 evidence, code-quality items | P1K-T3 | sonnet | sonnet |
| P1K-T5 | Out-of-framework LLM calls into the framework | Move `normalization/llm_review.py` (hardcoded gpt-4o-mini on a raw client — invisible to any retarget sweep) and `recipe_builder/generation.py` onto the provider framework (config-driven model, logging, retries, token accounting); seed the exemplar shuffle. | P6-M1, CC-8, D6 | — | sonnet | sonnet |

## Notes for spec authors

- T1's key-shape choice (raw sha vs `sha:{12}` prefix vs composite) is design-bearing:
  spec must fix it explicitly; profile_id remains `{package_id}/{sequence_file_id}`.
- T2's oracle supports both modes (LLM-assisted and pure-human review); default to
  human-reviewed batches — this loop exists to inject non-model truth.
- T3 must NOT invent a new format — `EffectRecipe` JSON + `index.json` as-is; only the
  location and tracking change.
