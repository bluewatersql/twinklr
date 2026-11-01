---
type: change
status: active
area: engineering
created: 2026-11-01
updated: 2026-11-01
---

# Runbook 02 — Phase 2K catalog growth (owner-data exit evidence)

**Purpose:** produce the remaining empirical Phase 2K (M2-K) exit evidence on the machine that
holds the owner's real xLights layout, sequence corpus, and style-group declaration.

**Satisfies (only when every step below passes and the evidence checklist in section 8 is
complete):**

| Exit gate | Task | Section |
|---|---|---|
| Real-layout coverage gap count is zero (element type x role x energy) | P2K-T1 | 4 |
| Idempotent real-corpus mining, unchanged rerun, non-empty distributions, exactly eight dated keep/change/defer decisions | P2K-T2 | 3 |
| Live targeted generation plus explicit human admit/reject sessions | P2K-T3 | 5 |
| Owner-declared per-style fingerprints, propensity rebuilt from stable identities, planner consumption verified on real data | P2K-T4 | 6 |

**This runbook operationalizes the specs; the specs win if they disagree.** Do not infer any
outcome: merged tooling and green offline tests are not empirical acceptance
([HANDOFF](../build/plan/HANDOFF.md), "Owner/local gates still pending" > "Phase 2K").

Authority:

- [P2K-T1 coverage report](../build/specs/phase-2k-catalog-growth/P2K-T1-coverage-report-tooling.md)
- [P2K-T2 mining runs and threshold review](../build/specs/phase-2k-catalog-growth/P2K-T2-mining-runs-and-threshold-review.md)
  (including "Offline owner-run readiness amendment" and "Formal rejection and remediation record")
- [P2K-T3 generation and curation sessions](../build/specs/phase-2k-catalog-growth/P2K-T3-llm-generation-curation-sessions.md)
- [P2K-T4 style fingerprints and propensity refresh](../build/specs/phase-2k-catalog-growth/P2K-T4-style-fingerprints-propensity-refresh.md)
- [Phase 2K plan](../build/plan/05-phase-2k-catalog-growth.md),
  [HANDOFF blocker #2 and "Phase 2K" gates](../build/plan/HANDOFF.md),
  [feature-engineering workflow](../../../scripts/docs/feature_engineering.md),
  [scripts inventory](../../../scripts/README.md)

Downstream: the accepted P2K-T2 evidence file produced in section 3 is artifact input for
[runbook 03 (P4-T7)](03-p4-t7-mh-idiom-mining.md). That task is optional and out of Phase 2K scope.

All commands run from the repository root. Every command and flag below was checked against
`--help` output or the argparse definitions in the current tree (see section 9 for what could
not be verified).

---

## 0. Read this first: traps that invalidate evidence

1. **Tracked-tree freeze between the two P2K-T2 mining runs.** The mining manifest hashes
   `git rev-parse HEAD`, the HEAD tree, and `git diff --binary HEAD` (tracked changes only).
   The unchanged-rerun proof (`verified_unchanged_rerun`) fails if any of these differ between
   run 1 and run 2. Do not commit, pull, checkout, or edit tracked files between them. Catalog
   promotion (sections 4-5) edits tracked files under `catalog/templates/`, which is why section 3
   (T2) comes first.
2. **Coverage must be measured against the tracked catalog only.** If `--catalog-dir` is omitted,
   the loader merges the untracked overlay `data/templates/` when it exists. Always pass
   `--catalog-dir catalog/templates` so the evidence reflects what is versioned in git.
3. **Never use `curate-catalog --promote` for Phase 2K.** It promotes every staged file with no
   per-candidate decision or reason. Promotion goes only through `review-staged-recipes` (section 5).
4. **Silent deterministic fallback.** `curate-catalog` without `--dry-run` and without
   `OPENAI_API_KEY` prints a warning and runs the deterministic generator (no LLM). A run that
   "worked" this way is not live-generation evidence. Section 5 includes a check.
5. **Licensing gate.** Mined or curated recipes must not be promoted unless you have confirmed
   you may redistribute them in this form
   ([catalog/templates/README.md](../../../catalog/templates/README.md), "Provenance and licensing
   gate"). Never commit vendor `.xsq`, `.zip`, `.xsqz`, audio, or media.
6. **Do not edit `FeatureEngineeringPipelineOptions` defaults or `config.py` to "apply" a
   threshold decision as part of this runbook.** The deliverable is the decision log. A change is a
   separate, explicitly approved diff (P2K-T2 spec, "Implementation approach").

### Recommended execution order

| Order | Section | Why |
|---|---|---|
| 1 | 1 Prerequisites, 2 Inputs | Nothing runs until inputs are in place |
| 2 | 3 P2K-T2 mining (two runs, report, decisions) | Needs a frozen tracked tree (trap 1) |
| 3 | 4 P2K-T1 baseline coverage, then curate | Read-only baseline first; promotion edits tracked files |
| 4 | 5 P2K-T3 generation and admission sessions (loop with 4) | Depends on the T1 coverage JSON |
| 5 | 6 P2K-T4 style fingerprints, propensity, planner check | Depends on T2; runs a fresh pair of mining runs |
| 6 | 7 Close-out, 8 Evidence checklist | |

---

## 1. Prerequisites

```bash
uv sync --extra dev --all-packages          # one-time; online
git status --porcelain                      # must print nothing before section 3
uv run twinklr --help                       # confirms: catalog-coverage, curate-catalog, review-staged-recipes
```

- Working directory is the repo root. `data/` is gitignored; everything under `data/owner/p2k/`
  below stays local.
- Python 3.13 per [conventions](../../../context/engineering/conventions.md).
- **Only section 5 needs network/credentials.** Everything else is offline.
- Choose and export one working root for the commands below:

```bash
export P2K=data/owner/p2k
mkdir -p "$P2K"/inputs/archives "$P2K"/inputs/layout "$P2K"/profiles "$P2K"/corpus \
         "$P2K"/mining "$P2K"/coverage "$P2K"/recipe_builder
```

---

## 2. Inputs you must supply (before anything runs)

| # | Input | Where to place it | Format | Used by |
|---|---|---|---|---|
| I1 | Real xLights layout | `$P2K/inputs/layout/rgbeffects.xml` | xLights `xlights_rgbeffects.xml` (the file the profiler parses as `rgbeffects.xml`) | T1, T3, T4 check |
| I2 | Real sequence corpus | `$P2K/inputs/archives/<name>.zip` or `.xsqz` (one file per sequence pack) | Vendor/own sequence packages: `.zip` or `.xsqz` containing a `.xsq` plus `xlights_rgbeffects.xml` | T2, T4 |
| I3 | Style-group declaration | `$P2K/inputs/style-groups.json` | JSON, schema below. Owner-authored, not inferred. Needed only for section 6 | T4 |
| I4 | `OPENAI_API_KEY` | Exported in your shell (`export OPENAI_API_KEY=...`); Twinklr does not auto-load `.env` | secret | T3 only |
| I5 | Your decisions | You author them (threshold decisions in section 3.7, admit/reject reasons in section 5) | | T2, T3 |

Corpus constraints enforced by owner mode (it fails, it does not repair): every sequence needs a
unique `(package_id, sequence_file_id)` and a unique `sequence_sha256`. Two archives that contain
byte-identical sequences are rejected as duplicate content identity, so deduplicate the archive set
yourself. There is no music-library index requirement; section 3 declares
`--no-music-library-index` explicitly (use `--music-library-index <path>` instead only if you have
one and want it bound into the fingerprint).

I3 schema (`twinklr.style-groups.v1`). Each group needs at least one selector; selectors are an
explicit union of `package_ids`, `sequence_file_ids`, and `sequence_keys`
(`<package_id>/<sequence_file_id>`). Names must produce unique slugs:

```json
{
  "schema_version": "twinklr.style-groups.v1",
  "groups": [
    {"style_name": "Warm Pop", "selector": {"package_ids": ["<content-hash-package-id>"]}},
    {"style_name": "Sparse Drama", "selector": {"sequence_keys": ["<package_id>/<sequence_file_id>"]}}
  ]
}
```

The IDs only exist after the corpus is built (section 3.2); section 6.1 prints them.

---

## 3. P2K-T2 — Idempotent real-corpus mining and threshold decisions (most detailed)

Spec: [P2K-T2](../build/specs/phase-2k-catalog-growth/P2K-T2-mining-runs-and-threshold-review.md).
This task is owner-decision-bearing: the tooling produces evidence; you author the decisions.
Offline, no paid calls, no network.

### 3.1 Profile each archive

One call per archive (the profiler has no batch mode over a custom directory; the no-argument form
only looks for `data/vendor_packages/example1..14`). Output goes to its own profile directory:

```bash
for f in "$P2K"/inputs/archives/*.zip "$P2K"/inputs/archives/*.xsqz; do
  [ -e "$f" ] || continue
  n="$(basename "${f%.*}")"
  uv run python scripts/demo_profiling.py --input "$f" --output-dir "$P2K/profiles/$n"
done
```

- Prints a summary table (status NEW/SKIP/ERROR, song, events, models). Re-running over an unchanged
  archive reports `SKIP` (cached); add `--force` only to force re-profiling.
- **Verify:** no `ERROR` rows; each `$P2K/profiles/<n>/` contains `sequence_metadata.json`,
  `base_effect_events.json`, `enriched_effect_events.json`, `effect_statistics.json`,
  `lineage_index.json`.
- Fix or remove any archive that errors; do not continue with a silently shrunken corpus. Record the
  final archive count.

### 3.2 Build the unified corpus (no CLI exists; minimal snippet)

Owner mode refuses to auto-build or fall back to global data, and the only builder
(`ProfileCorpusBuilder`) has no command-line entry point (its deprecation warning is expected):

```bash
uv run python - <<'PY'
import os
from pathlib import Path
from twinklr.core.profiling.unify import ProfileCorpusBuilder

root = Path(os.environ["P2K"])
results = ProfileCorpusBuilder().build(
    profiles_root=(root / "profiles").resolve(),
    output_root=(root / "corpus").resolve(),
)
for r in results:
    print(r.schema_version, r.profile_count, "profiles", r.sequence_count, "sequences ->", r.output_dir)
PY
```

- **Expected:** one result line (normally schema `v0_effectdb_structured_1`) and a directory
  `$P2K/corpus/<schema_version>/` holding `sequence_index.jsonl`, `corpus_manifest.json`,
  `lineage_index.jsonl`, `quality_report.json`, and event jsonl files. If two schema lines print,
  the corpus is mixed; mine one schema per run and record which.
- **Verify:** `sequence_count` equals the number of archives you intended.
- Set the corpus directory for the next steps (adjust the schema directory name to what printed):

```bash
export CORPUS="$P2K/corpus/v0_effectdb_structured_1"
```

### 3.3 Run 1 (cost: none, offline)

The output directory must not exist, and the feature store must live inside it. Keep the defaults for
the `--template-min-*` and `--quality-*` options: the point of the task is to look at the configured
constants as they are.

```bash
export RUN1="$P2K/mining/run-1"
uv run python scripts/demo_feature_engineering.py \
  --owner-mining-run \
  --no-music-library-index \
  --corpus-dir "$CORPUS" \
  --output-dir "$RUN1" \
  --feature-store-db "$RUN1/feature-store.sqlite"
```

- **Expected:** progress lines, `Built feature-engineering artifacts for N sequences`,
  `Wrote staged mining-run manifest: .../mining_run_manifest.json`, then the demo report
  (`feature_engineering_demo.md`) in the output directory. Exit code 0.
- **Verify run 1:** the manifest status must be `needs_identical_second_run`:

```bash
uv run python - <<'PY'
import json, os
from pathlib import Path
m = json.loads((Path(os.environ["RUN1"]) / "mining_run_manifest.json").read_text())
v = m["content_hash_identity"]["verification"]
print("status:", v["status"])                 # expect needs_identical_second_run
print("sequences:", m["sequence_count"])
print("catalog unchanged:", m["live_catalog_immutability"]["unchanged"])   # expect True
print("store after:", m["feature_store_snapshots"]["after"]["stats"])
PY
```

- **Failure modes (all fail closed):** missing/extra corpus file, duplicate logical or content
  identity, profile identity disagreeing with `sequence_index.jsonl`, output dir already existing
  without an owning manifest, output overlapping a protected root, symlink inside the output dir,
  `Live catalog changed during staged mining run`. Fix the cause and use a new output directory
  (or, only if run 1 aborted before writing a manifest, delete the half-made directory yourself).

### 3.4 Run 2 — the unchanged rerun (cost: none)

Do **not** edit any tracked file, commit, pull, or move the corpus/profile trees (trap 1). Repeat the
exact same command, same arguments, same output directory. The staged artifacts are rebuilt; the
SQLite store is preserved so the rerun can be compared against it:

```bash
uv run python scripts/demo_feature_engineering.py \
  --owner-mining-run \
  --no-music-library-index \
  --corpus-dir "$CORPUS" \
  --output-dir "$RUN1" \
  --feature-store-db "$RUN1/feature-store.sqlite"
```

Re-run the verification snippet from 3.3. **Pass condition:**

- `status: verified` and the manifest's `verified_unchanged_rerun` is `True`
- `duplicate_identity_count` is `0`
- `store after` stats equal run 1's `store after` stats (row counts did not grow); the manifest
  also binds stable entity-key and entity-content digests, which is why row counts alone are not
  the criterion

```bash
uv run python - <<'PY'
import json, os
from pathlib import Path
m = json.loads((Path(os.environ["RUN1"]) / "mining_run_manifest.json").read_text())
v = m["content_hash_identity"]["verification"]
for k in ("status", "verified_unchanged_rerun", "input_fingerprint_matches_previous",
          "source_provenance_matches_previous", "entity_key_digests_match",
          "entity_content_digests_match", "duplicate_identity_count",
          "before_matches_previous_after", "after_matches_before"):
    print(f"{k}: {v[k]}")
print("catalog unchanged:", m["live_catalog_immutability"]["unchanged"])
PY
```

If `status` is `changed`: read which boolean is False. `source_provenance_matches_previous=False`
means the tracked tree moved between runs; restore it and delete the whole `$RUN1` directory, then
start over from 3.3 (a corrupted store comparison cannot be repaired by rerunning). If
`input_fingerprint_matches_previous=False`, the corpus or profile trees changed; same remedy. A
rerun must never be accepted as "close enough".

**Evidence to record:** `mining_run_manifest.json` (keep it local; it contains absolute paths) and
its SHA-256 (`shasum -a 256 "$RUN1/mining_run_manifest.json"`); the stdout of both runs (save with
`| tee "$P2K/mining/run-1-stdout-N.log"` if you want it).

### 3.5 Generate the distribution report and decision template

The reporting script fails unless run 2 proved the unchanged rerun and live-catalog immutability.
Run it **once** after run 2 (a second invocation regenerates the review bundle with a new hash and
makes any already-filled decision file stale):

```bash
uv run python scripts/report_quality_gate_distributions.py --run-dir "$RUN1"
```

**Writes (inside `$RUN1`):** `quality_gate_distribution_report.json` and `.md`,
`quality_gate_review_bundle.json` (hash-binds the mining manifest, staged candidates, promotion
report, distribution reports), and `OWNER_DECISIONS.json` (template, written only if absent).
It never promotes anything and never edits thresholds.

**Verify non-empty distributions** (the tool does not assert this; you must). Expect a positive
`candidate_count` and non-zero bucket sums for all three histograms:

```bash
uv run python - <<'PY'
import json, os
from pathlib import Path
r = json.loads((Path(os.environ["RUN1"]) / "quality_gate_distribution_report.json").read_text())
print("candidate_count:", r["candidate_count"])
print("population:", r["candidate_population"])
for name, h in r["histograms"].items():
    print(name, "total", sum(h.values()), h)
print("effective gates:", r["recipe_promotion"]["effective_applied"])
print("static gates:   ", r["recipe_promotion"]["static_configured"])
print("discrepancy:", r["promotion_default_discrepancy"])
for name, row in r["threshold_review"]["numeric_values"].items():
    print(name, "| configured:", row["configured"], "| status:", row["status"],
          "| sensitivity points:", len(row["sensitivity"]))
PY
```

If `candidate_count` is 0 or a histogram sums to 0, the corpus produced nothing reviewable. That is
a finding, not a pass: do not fill in decisions; record it and enlarge or fix the corpus.

Read `quality_gate_distribution_report.md`. It surfaces, as the spec requires: histograms of
`support_count`, `cross_pack_stability`, and `distinct_pack_count` across all candidates; the
effective (adaptive) gates versus the static config; pass/fail sensitivity at the configured value
plus two nearby values for each of the eight numbers; the low-pack-count risk among gate passes
(P6's flagged failure mode); and the `PromotionPipeline.run()` defaults (5 / 0.3) versus the
configured pipeline values (2 / 0.015), which is an explicit owner line item, not silently
reconciled. Any numeric value whose `status` is not `available` has no usable sensitivity evidence;
decide `defer` for it and say why.

### 3.6 Review (owner-authored, human only)

You are the decider. Nothing here can be filled in by an agent or a script ([P2K-T2](../build/specs/phase-2k-catalog-growth/P2K-T2-mining-runs-and-threshold-review.md),
"Acceptance criteria": "authored during the owner's session, not fabricated post hoc by an agent").
The eight values, in the template's order:

1. `recipe_promotion_min_support`
2. `recipe_promotion_min_stability`
3. `promotion_run_default_min_support` (the `PromotionPipeline.run()` 5 vs configured 2 gap)
4. `promotion_run_default_min_stability` (0.3 vs configured 0.015)
5. `propensity_min_support`
6. `target_role_score_cutoff`
7. `recipe_promotion_max_per_family`
8. `recipe_promotion_max_per_cluster`

### 3.7 Complete `OWNER_DECISIONS.json`

Edit `$RUN1/OWNER_DECISIONS.json` by hand. Leave `schema_version`, the report/bundle hash fields,
`name`, and `current_value` untouched. Exactly eight entries must remain (no add/remove/duplicate).
For each entry:

| Field | Rule |
|---|---|
| `decision` | exactly `"keep"`, `"change"`, or `"defer"` (the placeholder `"<keep\|change\|defer>"` is invalid) |
| `changed_value` | `null` unless `decision` is `"change"`, in which case a number is required. Integer >= 1 for `recipe_promotion_min_support`, `promotion_run_default_min_support`, `propensity_min_support`, `recipe_promotion_max_per_family`, `recipe_promotion_max_per_cluster`; a float in [0, 1] for `recipe_promotion_min_stability`, `promotion_run_default_min_stability`, `target_role_score_cutoff`. Always write floats with a decimal point (`1.0`, `0.05`); the strict model rejects `1` or `0` |
| `decided_on` | the real date of your decision, `YYYY-MM-DD` (replaces `"<YYYY-MM-DD>"`) |
| `rationale` | non-blank text of your own, citing the evidence you read |

A `change` here only records intent. It does not alter code (trap 6).

### 3.8 Bind the decisions into accepted evidence

```bash
uv run python scripts/report_quality_gate_distributions.py \
  --run-dir "$RUN1" --bind-owner-decisions --accepted-on YYYY-MM-DD
```

- **Expected:** `Evidence manifest: $RUN1/quality_gate_evidence_manifest.json`, schema
  `twinklr.p2k-evidence.v2` with `accepted: true`. Binding re-hashes the mining manifest, staged
  candidates, promotion report, and both distribution reports, and rejects a stale, regenerated, or
  tampered input, a stale `current_value`, or an invalid decision file with a specific error.
- **If it rejects as stale:** you regenerated the report after filling in decisions. Copy your
  rationales elsewhere, delete `OWNER_DECISIONS.json`, rerun the section 3.5 command, and re-enter.
- Do not rerun `demo_feature_engineering.py` against `$RUN1` after this point: it cleans the
  directory and deletes the decision file and evidence manifest.

**Evidence to record for T2** (see section 7 for where): `OWNER_DECISIONS.json`,
`quality_gate_evidence_manifest.json`, `quality_gate_review_bundle.json`,
`quality_gate_distribution_report.json`/`.md`, and the SHA-256 of `mining_run_manifest.json`.

---

## 4. P2K-T1 — Coverage against the real layout; curate to zero gaps

Spec: [P2K-T1](../build/specs/phase-2k-catalog-growth/P2K-T1-coverage-report-tooling.md). Read-only,
offline, no cost.

### 4.1 Baseline report

```bash
uv run twinklr catalog-coverage \
  --layout "$P2K/inputs/layout/rgbeffects.xml" \
  --catalog-dir catalog/templates \
  --out "$P2K/coverage/coverage-0.json"
```

- **Expected stdout:** a header stating only BASE, RHYTHM, ACCENT are covered (TRANSITION and
  SPECIAL excluded by design, PEAK outside the five-value energy axis), one block per layout
  element type ranked by pixel prominence with GAP or recipe counts per role x energy cell, an
  "Unclassified display models (action required)" block if any, and a final line
  `Summary: X/Y cells covered; G gaps; exit criterion met: <bool>.` JSON is written to `--out`. The
  command exits 0 even with gaps; read the summary.
- It does not modify the catalog or layout.

### 4.2 Interpret it

```bash
uv run python - <<'PY'
import json, os
from pathlib import Path
r = json.loads((Path(os.environ["P2K"]) / "coverage" / "coverage-0.json").read_text())
print("summary:", r["summary"])
print("element types:", [(e["element_type"], round(e["prominence_share"], 3)) for e in r["element_types"]])
print("unclassified:", r["unclassified"])
print("top gaps:", [(g["element_type"], g["role"], g["energy"]) for g in r["gaps"][:10]])
PY
```

**Exit pass for T1 requires both:** `summary.gap_cells == 0` (`exit_criterion_met: true`) **and**
`unclassified == []`. The tool deliberately excludes unclassified models from the pass/fail
ratio and only warns, so an unclassified model hides uncovered layout from the headline number.
If models are unclassified, the pattern table in
`packages/twinklr/core/feature_engineering/element_types.py` lacks an entry for your model names;
extending it is a code change that this runbook does not perform (see section 9, gap (a)3).
Record the disposition (extended, or each model explicitly justified as out of scope) alongside the
report.

A recipe with `model_affinities == []` counts for every element type; one with a non-empty list
counts only for listed types with `score > 0`. A generated recipe that lists only other element
types will not close your gap even if its role and energy match.

### 4.3 Curate

Gaps are closed through the generation and admission loop in section 5, using this JSON as input.
After every promotion session, re-run 4.1 with the next file name (`coverage-1.json`, ...) and
repeat until the exit pass in 4.2. Keep every intermediate report.

The spec defines no tool for admitting mined candidates (`recipe_catalog.json` from section 3) or
hand-authored recipes into `catalog/templates/`; see section 9, gap (a)1.

### 4.4 Version the catalog with provenance (exit clause "catalog versioned in git with provenance")

After each accepted session (after section 3 is finished, so trap 1 no longer applies), review and
commit the catalog yourself:

```bash
git status --short catalog/templates
git diff --stat catalog/templates
git add catalog/templates
git commit -m "feat(catalog): admit <n> recipes for <element types> (P2K session <id>)"
```

Provenance is each recipe's own `provenance.source` plus the session log (section 5) naming the
human decision and reason. Re-confirm the licensing gate (trap 5) before committing.

---

## 5. P2K-T3 — Live targeted generation and human admission sessions

Spec: [P2K-T3](../build/specs/phase-2k-catalog-growth/P2K-T3-llm-generation-curation-sessions.md).

> **LIVE / PAID.** 5.2 and 5.3 call the OpenAI-backed provider (default model `gpt-5.6-sol`,
> `reasoning_effort` high, temperature 0.9, `max_tokens` 50000 per response). **Everything else in
> this runbook is offline.** The spec ("Verification commands") calls this "LOCAL-ONLY, owner
> session, real cost" but defines **no numeric cost cap and no authorization record**, and the tool
> enforces none. You must set your own cap before 5.3 (open decision 1 in section 9). Cost drivers:
> one request per opportunity, the provider can retry failed attempts, and a coverage-report run
> adds one opportunity **per gap cell** on top of `--max-opportunities` (that flag caps only the
> catalog-internal opportunities).

### 5.1 Dry run: count opportunities, zero cost

Deterministic fallback, analysis phase only, catalog-internal opportunities disabled, so the output
is exactly the coverage gaps:

```bash
uv run twinklr curate-catalog \
  --run-name p2k-plan \
  --output-dir "$P2K/recipe_builder" \
  --templates-dir catalog/templates \
  --coverage-report "$P2K/coverage/coverage-0.json" \
  --max-opportunities 0 \
  --phase analysis --dry-run

uv run python - <<'PY'
import json, os
from pathlib import Path
o = json.loads((Path(os.environ["P2K"]) / "recipe_builder/p2k-plan/opportunities.json").read_text())
opps = o["opportunities"]
print("opportunities (= LLM requests in 5.3):", len(opps))
for x in opps[:10]:
    print(x["opportunity_id"], x["priority"])
PY
```

To bound spend, generate for the top-N gaps only: make a trimmed copy of the coverage JSON (the
loader reads only `element_types` and `gaps`) and pass that copy as `--coverage-report`:

```bash
uv run python - <<'PY'
import json, os
from pathlib import Path
N = 10   # your cap
root = Path(os.environ["P2K"]) / "coverage"
r = json.loads((root / "coverage-0.json").read_text())
r["gaps"] = r["gaps"][:N]
(root / "coverage-0-top.json").write_text(json.dumps(r, indent=2) + "\n")
print("kept", len(r["gaps"]), "gaps")
PY
```

### 5.2 Authorize and set credentials

Record your cap (requests and USD) and the date before continuing; this is the authorization the
spec leaves to you. Then:

```bash
export OPENAI_API_KEY=...   # in your shell only
```

### 5.3 Live generation (PAID)

```bash
uv run twinklr curate-catalog \
  --run-name p2k-gen-01 \
  --output-dir "$P2K/recipe_builder" \
  --templates-dir catalog/templates \
  --fe-dir "$RUN1" \
  --coverage-report "$P2K/coverage/coverage-0-top.json" \
  --max-opportunities 0
```

`--model`, `--temperature`, and `--reasoning-effort {low,medium,high}` default to the sol-tier
config shown in `--help`; pass `--model` only if your key's catalog needs a different name. Do not
pass `--promote`. The run is staged only. (`--fe-dir "$RUN1"` is optional context; it must be a
mining run without `--style-groups`, otherwise the loader warns and the run proceeds with no FE
evidence.)

- **Expected:** `Run complete. Review staged artifacts in .../p2k-gen-01`, exit 0. Artifacts in
  `$P2K/recipe_builder/p2k-gen-01/`: `opportunities.json`, `generated_recipe_candidates.json`,
  `validation_report.json`, `admission_report.json`, `staged_recipes/*.json`, `run_manifest.json`.
- **Verify it was actually live** (trap 4) and see what reached staging:

```bash
uv run python - <<'PY'
import json, os
from collections import Counter
from pathlib import Path
d = Path(os.environ["P2K"]) / "recipe_builder/p2k-gen-01"
c = json.loads((d / "generated_recipe_candidates.json").read_text())["candidates"]
print("generation modes:", Counter(x["generation_mode"] for x in c))   # want all 'llm'
print("staged files:", len(list((d / "staged_recipes").glob("*.json"))))
print("admission counts:", json.loads((d / "admission_report.json").read_text())["counts"])
PY
```

If modes show `deterministic`, the key was missing; fix and use a new `--run-name`. Opportunities
whose LLM output failed validation are logged and skipped, so candidates can be fewer than
requests. Candidates the deterministic validator rejects never reach `staged_recipes/`, so they get
no human decision.

### 5.4 Human admission session (offline; interactive)

```bash
uv run twinklr review-staged-recipes \
  --run-dir "$P2K/recipe_builder/p2k-gen-01" \
  --templates-dir catalog/templates \
  --session-id p2k-session-01
```

For every staged candidate it prints the recipe summary plus the automated admission decision, then
prompts `Human decision [admit/reject]:` and `Reason (required):`. There is no default and no skip.

- Type exactly `admit` or `reject` (case-insensitive after trimming) and a non-blank reason. **Any
  other input aborts the whole session with an error and writes no log**, as does Ctrl-C/EOF
  (`Curation aborted: no session log was written and no recipes were promoted`). Review in small
  batches (one generation run of about 10 candidates) so an abort costs little.
- After the last prompt it writes the log, then promotes exactly the admitted `recipe_id`s into
  `catalog/templates/builtins/` and `index.json`.
- `--session-id` must be unique per run directory (an existing log is refused, not overwritten).
  Re-running on the same staged directory re-prompts every candidate; already-promoted IDs are
  skipped as already indexed.
- This step is the only path in the tooling that calls promotion, and only with a human-authored ID
  set.

**Expected output:** `Session log: .../curation_sessions/p2k-session-01.json`, `Reviewed: N`,
`Promoted (K): [...]`, `Not promoted (...)`.

**Verify and record:**

```bash
uv run python - <<'PY'
import json, os
from pathlib import Path
p = Path(os.environ["P2K"]) / "recipe_builder/p2k-gen-01/curation_sessions/p2k-session-01.json"
log = json.loads(p.read_text())
rows = log["records"]
print("reviewed:", len(rows), "admitted:", sum(r["human_decision"] == "admit" for r in rows))
assert all(r["reason"].strip() for r in rows)
PY
```

The session log is the T3 evidence: one row per candidate with `recipe_id`, `opportunity_category`,
`target_element_type`, `automated_decision`, `human_decision`, `reason`, `timestamp`. Reject reasons
are the input to later prompt refinement; revising `SYSTEM_PROMPT` from them is separate, owner-led
work and not part of this runbook.

### 5.5 Loop

Return to 4.1 (new coverage file), then repeat 5.1 to 5.4 with new run names and session IDs until
the 4.2 exit pass holds. Commit per 4.4. Keep every run directory and log.

### T3 acceptance summary

- `review-staged-recipes` required an explicit admit/reject plus reason for every staged candidate
- promoted IDs equal the admitted set (compare `Promoted` output with the log)
- session log(s) exist under `curation_sessions/`
- at least one generation run was `generation_mode: llm` and targeted gap cells (check
  `target_element_type` is set in the log rows)

---

## 6. P2K-T4 — Style fingerprints, propensity refresh, planner consumption

Spec: [P2K-T4](../build/specs/phase-2k-catalog-growth/P2K-T4-style-fingerprints-propensity-refresh.md).
Offline, no cost. The style grouping is your input; do not let anyone fabricate it.

### 6.1 List the stable identities, then write I3

```bash
uv run python - <<'PY'
import json, os
from pathlib import Path
corpus = Path(os.environ["CORPUS"])
for line in (corpus / "sequence_index.jsonl").read_text().splitlines():
    r = json.loads(line)
    print(r["package_id"], r["sequence_file_id"], "|", r.get("song"), "|", r.get("artist"))
PY
```

Write `$P2K/inputs/style-groups.json` (schema in section 2). A missing or invalid file makes the
run fail loudly (`style-group declaration is required and was not found`), as the spec requires.

### 6.2 Fresh mining run with style groups (pair, offline)

A fresh output directory keeps T2's accepted evidence intact (re-running into `$RUN1` would delete
it). The tracked tree must again be unchanged across the pair (trap 1): commit any section 4-5
catalog changes first, then do not touch the tree until after run B.

```bash
export RUN2="$P2K/mining/run-styled"
uv run python scripts/demo_feature_engineering.py \
  --owner-mining-run \
  --no-music-library-index \
  --corpus-dir "$CORPUS" \
  --output-dir "$RUN2" \
  --feature-store-db "$RUN2/feature-store.sqlite" \
  --style-groups "$P2K/inputs/style-groups.json"
# repeat the identical command once more
```

`--style-groups` cannot be combined with `--skip-build`. Propensity is rebuilt once over the full
corpus (not per style). The repeat gives the same `verified` proof as 3.4 for the propensity
rebuild ("no duplicate-row inflation"); check it with the 3.4 snippet pointed at `$RUN2`
(`RUN1="$RUN2"`).

**Expected artifacts in `$RUN2`:** `propensity_index.json`, one
`style_fingerprint_<slug>.json` per declared group, `style_fingerprint_report.json`,
`feature_store_manifest.json` (its `style_fingerprints` object maps style name to file).

### 6.3 Check fingerprints for thin support

```bash
uv run python - <<'PY'
import json, os
from pathlib import Path
rep = json.loads((Path(os.environ["RUN2"]) / "style_fingerprint_report.json").read_text())
for s in rep["styles"]:
    print(s["style_name"], "| sequences:", s["corpus_sequence_count"],
          "| phrases:", s["phrase_count"], "| thin:", s["thin"])
PY
```

`thin` means fewer than 2 source sequences (a hardcoded reporting threshold; the artifact is still
written). Each group's `corpus_sequence_count` must reflect that group's own support, not the whole
corpus. Decide, and record, whether thin styles are acceptable for your "preferred styles" claim.

### 6.4 Verify planner consumption on real data (offline snippet; no dedicated tool)

Loads each fingerprint through `load_fe_artifacts` (a grouped run requires an explicit
`style_name`) and runs the planner stage's own context extraction, the same read path
`group_planner/stage.py` uses. Also compares propensity coverage against your layout's element types
from `coverage-0.json` (this comparison is a convenience check, not a spec-defined tool):

```bash
uv run python - <<'PY'
import json, os
from pathlib import Path
from twinklr.core.agents.sequencer.group_planner.stage import GroupPlannerStage
from twinklr.core.feature_engineering.loader import load_fe_artifacts

fe = Path(os.environ["RUN2"])
layout_types = {e["element_type"] for e in json.loads(
    (Path(os.environ["P2K"]) / "coverage" / "coverage-0.json").read_text())["element_types"]}
styles = [s["style_name"] for s in json.loads((fe / "style_fingerprint_report.json").read_text())["styles"]]
for name in styles:
    bundle = load_fe_artifacts(fe, style_name=name)
    assert bundle.propensity_index is not None and bundle.style_fingerprint is not None, name
    stage = GroupPlannerStage(choreo_graph=None, template_catalog=None, fe_bundle=bundle)
    fields = stage._extract_fe_fields(section_id="verse_1")
    hints = fields.get("propensity_hints") or {}
    print(name, "| propensity affinities:", len(hints.get("affinities", [])),
          "| style_constraints keys:", sorted(fields.get("style_constraints", {})),
          "| fingerprint sequences:", bundle.style_fingerprint.corpus_sequence_count)
    assert hints.get("affinities") and fields.get("style_constraints"), f"empty planner context for {name}"
covered = {a.model_type for a in bundle.propensity_index.affinities}
print("layout element types with no propensity affinity:", sorted(layout_types - covered) or "none")
PY
```

- **Pass:** no assertion error for any declared style; `propensity_hints` and `style_constraints`
  are non-empty for each.
- **"Populated per element type" (plan exit clause):** the final line lists layout element types
  that have zero propensity affinity rows. The spec gives no tooling and no numeric definition of
  "populated"; my working definition is at least one affinity row per layout element type. Adopt
  it or state another (open decision 3 in section 9). Types absent from the corpus are a data gap
  to record, not something to fabricate.
- `GroupPlannerStage._extract_fe_fields` is a private method; this snippet will need updating if it
  is renamed. The stage construction passes `None` for `choreo_graph`/`template_catalog` because
  they are unused on this path.

### 6.5 Planner selection (documentation of the shipped mechanism)

Multi-fingerprint selection is already implemented: `twinklr display` and `twinklr show` take
`--fe-output-dir <dir>` plus `--style "<style name>"`; omitting `--style` on a grouped output
raises with the available names (verified in `load_fe_artifacts` and `display_cmd.py`). Actually
running those commands calls the paid planner and is outside this runbook; 6.4 is the offline
consumption proof.

---

## 7. Evidence recording and close-out

Where evidence lives follows the specs: P2K-T2's decision log belongs under
`changes/twinklr-reactivation-review/` "or a phase-2K-specific home the orchestrator designates"
and **not** in `memories/`; `evaluations/` is reserved for `eval-report` output
([evaluations/README.md](../../../evaluations/README.md)). Proposed home (confirm with the
orchestrator, open decision 4):
`changes/twinklr-reactivation-review/evidence/phase-2k/`.

Copy only small, non-private, reviewable files there; never copy corpus, profiles, the feature-store
SQLite, vendor archives, or audio:

| Evidence file | Source |
|---|---|
| `OWNER_DECISIONS.json`, `quality_gate_evidence_manifest.json`, `quality_gate_review_bundle.json` | `$RUN1` |
| `quality_gate_distribution_report.json` / `.md` | `$RUN1` |
| `mining_run_manifest.json` SHA-256 line (the file itself holds absolute paths; keep local unless you are comfortable publishing them) | `$RUN1` |
| coverage reports `coverage-0.json` ... final (contain your layout model names) | `$P2K/coverage/` |
| curation session logs `curation_sessions/*.json` and each run's `run_manifest.json` | `$P2K/recipe_builder/<run>/` |
| `style_fingerprint_report.json`, the style-groups declaration, the 6.4 console output | `$RUN2`, inputs |
| the console output of the verification snippets | saved by you |

Then, per [AGENTS.md](../../../AGENTS.md) "Definition of done": have the orchestrating agent (not
this runbook) update the change artifacts and [HANDOFF](../build/plan/HANDOFF.md), mark Phase 2K
status in [ACTIVE.md](../../ACTIVE.md), file accepted threshold decisions that changed a constant
into `memories/decisions/` at phase close, and run the independent verification the specs require
(P2K-T2 and P2K-T4 verifier: opus). This runbook records no outcome by itself.

`make validate` is only required if you also change code (for example the element-type pattern
table or a threshold constant), which are separate approved diffs.

---

## 8. Evidence checklist (exit criterion to proving artifact)

| # | Exit criterion | Proving artifact | Pass condition |
|---|---|---|---|
| 1 | Real-layout coverage, zero gaps (T1; plan exit clause 1) | Final `coverage-N.json` + stdout | `summary.gap_cells == 0`, `exit_criterion_met: true`, and `unclassified == []` (or each disposition recorded) |
| 2 | Catalog versioned in git with provenance (plan exit clause 4) | Git commit(s) touching `catalog/templates/`; session logs | Commit exists; each admitted recipe traces to a log row and `provenance.source` |
| 3 | Real-corpus mining completed, staged only (T2) | `$RUN1/mining_run_manifest.json` (+ SHA-256 recorded) | Run 1 manifest valid; `live_catalog_immutability.unchanged == true`; corpus count equals intended |
| 4 | Unchanged-corpus rerun proving content-level idempotence (T2) | Same manifest after run 2 | `status == "verified"`, `verified_unchanged_rerun == true`, `duplicate_identity_count == 0`, digests match |
| 5 | Non-empty empirical distributions (T2) | `quality_gate_distribution_report.json` / `.md` | `candidate_count > 0`, all three histogram sums > 0 |
| 6 | Sensitivity at configured + 2 nearby values for each of the eight values; 5/0.3 vs 2/0.015 discrepancy called out (T2) | Same report, `threshold_review.numeric_values`, `promotion_default_discrepancy` | Each of the eight has `status` available and 3 sensitivity points (or a documented `defer`) |
| 7 | Exactly eight dated keep/change/defer decisions with rationales, owner-authored (T2) | `OWNER_DECISIONS.json` | Validated by the bind step (exactly eight, typed, dated, rationales) |
| 8 | Accepted, hash-bound P2K evidence (T2; also runbook 03 input) | `quality_gate_evidence_manifest.json` | Schema `twinklr.p2k-evidence.v2`, `accepted: true`, `accepted_on` date |
| 9 | No live catalog change by mining (T2) | Manifest `live_catalog_immutability` | `unchanged == true` for both runs |
| 10 | Live targeted generation (T3) | `generated_recipe_candidates.json`, `run_manifest.json`, your cap record | `generation_mode == "llm"`; opportunities came from gap cells; spend within your cap |
| 11 | Explicit human admit/reject with reasons; promotion only of admitted IDs (T3) | `curation_sessions/<id>.json` + `Promoted` console output | One row per staged candidate, non-blank reasons; promoted == admitted |
| 12 | Owner-declared per-style fingerprints (T4; plan exit clause 3) | `style_fingerprint_<slug>.json` per group, `style_fingerprint_report.json`, the declaration | One valid fingerprint per declared group; `corpus_sequence_count` per group; thin groups flagged and dispositioned |
| 13 | Propensity rebuilt from stable identities, no duplicate inflation (T4) | `$RUN2` manifest (pair of identical runs) | `status == "verified"`, `duplicate_identity_count == 0` |
| 14 | Propensity/affinity populated per element type (plan exit clause 2) | 6.4 output | Listed layout element types without affinities is empty, or each is dispositioned |
| 15 | Planner consumption on real data (T4) | 6.4 output | No assertion failure; non-empty `propensity_hints` and `style_constraints` per style |
| 16 | Independent verification | Verifier report (opus for T2 and T4, sonnet for T1 and T3) | Done by the orchestrator, not by this runbook |

---

## 9. Verification status, tooling gaps, open decisions

**Verified (read from current code and `--help`):** `twinklr catalog-coverage`,
`twinklr curate-catalog`, `twinklr review-staged-recipes`,
`scripts/demo_profiling.py`, `scripts/demo_feature_engineering.py`,
`scripts/report_quality_gate_distributions.py` flags; the manifest, report, and decision schemas;
owner-mode path rules; `GroupPlannerStage` construction and `_extract_fe_fields` with an empty
bundle; `ProfileCorpusBuilder.build` against an empty profiles root.

**Not executed here (no owner data, and no paid or write steps were allowed):** every step against
real inputs. The Python snippets in 3.2 (on real data), 3.5, 4.2, 5.1, 5.3, 5.4, 6.1, 6.3, 6.4 were
checked against the code's field names but not run on real artifacts. In particular I could not
confirm that a real run emits every file the report script requires (`promotion_report.json`,
`cluster_candidates.json`, `effect_phrases.*`, `target_roles.*`); the script names the missing
file in its error if one is absent.

**Spec requirements without tooling (a):**

1. Admitting **mined** candidates (the `recipe_catalog.json` from FE runs) into
   `catalog/templates/` with a human decision and reason. T3's tool covers only the generation arm,
   and T2 stages mining output only. The exit criterion is "grown by both supply arms", so a gap
   remains if you want mined recipes in the catalog.
2. A unified-corpus build command. `ProfileCorpusBuilder` is a deprecated library class; the 3.2
   snippet is the only route.
3. Fixing **unclassified** layout models: requires editing the pattern table in
   `feature_engineering/element_types.py` (code change).
4. A cost/request cap or authorization record for live generation: none in tooling or spec; the
   gap-opportunity count is not bounded by `--max-opportunities`.
5. "Propensity/affinity data populated per element type": no tool and no defined threshold; 6.4 is
   an improvised check.
6. Non-empty-distribution assertion: the report does not fail on zero candidates; 3.5 is a manual
   check.
7. Applying a threshold `change` decision to code: intentionally out of scope (trap 6).

**Owner decisions left open (c):**

1. Live-generation budget (USD and request count) and authorization record, section 5.2.
2. The unit of the T1 pass: whether `unclassified == []` is required (this runbook requires it or a
   per-model disposition).
3. Definition of "populated per element type" and the acceptable minimum for thin style
   fingerprints (spec flags fewer than 2 sequences).
4. Final evidence home and how much of the manifest data (absolute paths, layout model names) you
   are willing to commit.
5. Which archives constitute the corpus, which schema directory to mine, and the music-library-index
   choice (`--no-music-library-index` assumed).
6. The eight threshold decisions and the style-group declaration themselves.
7. Whether to run sections 5 and 6 to completion before or after committing catalog changes
   (this runbook orders T2 first for the git-diff reason in trap 1).
