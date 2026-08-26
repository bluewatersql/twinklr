# Feature Engineering

> **Canonical guide**: See [`docs/pipeline_guide.md`](../../docs/pipeline_guide.md) for the
> comprehensive pipeline reference. This file is a quick-reference summary.

## Supported feature-engineering entry point

The historical `scripts/build/` orchestrator was removed. There is no supported
zero-argument discover/profile/mine command in the current tree. Build a unified profile
corpus with the profiling workflow first, then pass that corpus explicitly to the
feature-engineering demo. A unified corpus contains `sequence_index.jsonl`,
`corpus_manifest.json`, and `lineage_index.jsonl`; each indexed profile contains the
five profile identity/artifact files checked by owner-run mode.

## Run feature engineering and demo reporting

Script:
- `scripts/demo_feature_engineering.py`

Exploratory build + report:

```bash
python scripts/demo_feature_engineering.py \
  --corpus-dir data/profiles/corpus/v0_effectdb_structured_1 \
  --output-dir data/features/demo_feature_engineering
```

Report only (no build):

```bash
python scripts/demo_feature_engineering.py \
  --skip-build \
  --output-dir data/features/demo_feature_engineering
```

Demo report output:
- `feature_engineering_demo.md`

The demo surfaces:
- per-sequence coverage with `sequence_name` (song)
- duplicate-sequence warning by `sequence_sha256`
- taxonomy/role distributions
- top content/orchestration templates
- template retrieval baseline ranking
- template diagnostics (low support/high concentration/high variance/over-generic flags)
- transition graph summary
- quality gate summary

## Owner mining and threshold-review session

The feature-engineering output directory is a **staging area**, not the live
recipe catalog. For an owner-local corpus session, run the demo with a dedicated
output directory and SQLite feature store, then run it a second time unchanged
before reviewing thresholds. Owner mode requires an explicit unified corpus and refuses
an existing output directory unless its prior manifest proves that it owns the same path
and exact corpus/profile/music input fingerprint. It never falls back to global data.

```bash
uv run python scripts/demo_feature_engineering.py \
  --owner-mining-run \
  --no-music-library-index \
  --corpus-dir <author-local-corpus> \
  --output-dir <staged-mining-run> \
  --feature-store-db <staged-mining-run>/feature-store.sqlite

# Repeat the exact same command. The embedded store is preserved while staged
# artifacts are rebuilt, and the second manifest must report status=verified.
uv run python scripts/demo_feature_engineering.py \
  --owner-mining-run \
  --no-music-library-index \
  --corpus-dir <author-local-corpus> \
  --output-dir <staged-mining-run> \
  --feature-store-db <staged-mining-run>/feature-store.sqlite

uv run python scripts/report_quality_gate_distributions.py \
  --run-dir <staged-mining-run>
```

The manifest binds the corpus manifest/index/lineage, every indexed profile tree, the
optional local music index, tool files, Git commit/tree/diff, staged artifact hashes, and
stable feature-store entity-key/content digests. Duplicate logical identities or content
digests fail before mining. The second run must record
`verified_unchanged_rerun: true`; row counts alone are not sufficient.

Use `--music-library-index <absolute-or-relative-path>` instead of
`--no-music-library-index` when music metadata participates in the run. Owner mode requires
one of those declarations so a hidden global index cannot change the result.

The reporting command fails unless that rerun and live-catalog immutability are proven.
It writes JSON/Markdown distributions, a hash-bound review bundle, and strict
`OWNER_DECISIONS.json`. The owner must fill one dated keep/change/defer decision and
rationale for every numeric value, then finalize the hash binding:

```bash
uv run python scripts/report_quality_gate_distributions.py \
  --run-dir <staged-mining-run> \
  --bind-owner-decisions \
  --accepted-on YYYY-MM-DD
```

Finalization rejects blank, malformed, missing, extra, stale, regenerated, or tampered
decisions and artifacts, then writes the compact accepted
`quality_gate_evidence_manifest.json`. Its hashes bind the exact review bundle and
completed decision record.
No command promotes a candidate or modifies `catalog/templates/`.

## Moving-head corpus prerequisite

P4-T7 remains deferred until the owner creates a private, gitignored or out-of-repository
`twinklr.mh-corpus-manifest.v1` file and explicitly declares sufficiency. Validate only
its file identities and provenance, without parsing sequence content:

```json
{
  "schema_version": "twinklr.mh-corpus-manifest.v1",
  "corpus_id": "<owner-local-id>",
  "created_at_utc": "<ISO-8601 timestamp>",
  "entries": [{
    "package_id": "<stable package id>",
    "sequence_file_id": "<stable sequence id>",
    "vendor": "<source vendor>",
    "source_kind": "owner_local_vendor_archive",
    "archive_path": "<absolute path>",
    "archive_sha256": "<64 hex characters>",
    "sequence_path": "<absolute path>",
    "sequence_sha256": "<64 hex characters>",
    "fixture_families": ["<family>"],
    "fixture_roles": ["<role>"]
  }],
  "sufficiency": {
    "decision": "sufficient",
    "declared_by": "<owner>",
    "declared_at_utc": "<ISO-8601 timestamp>",
    "minimum_sequences": 1,
    "minimum_vendors": 1,
    "minimum_fixture_families": 1,
    "minimum_fixture_roles": 1,
    "rationale": "<why this corpus is or is not enough for the time-boxed spike>"
  }
}
```

```bash
uv run python scripts/validate_mh_corpus_manifest.py \
  --manifest <owner-local-mh-manifest.json> \
  --p2k-evidence <staged-mining-run>/quality_gate_evidence_manifest.json \
  --evidence-out <owner-local-output>/mh-corpus-evidence.json \
  --require-sufficient
```

The shareable evidence file contains the private manifest hash, the exact accepted P2K
evidence hash, aggregate variety counts, declared minima, and the sufficiency decision;
it omits paths, vendors, sequence IDs,
fixture labels, source digests, owner identity, and rationale text. This validator does
not satisfy P4-T7 by itself.

## Owner-selected style fingerprints

Style groups are owner declarations, never inferred from corpus content.
`--style-groups <declaration.json>` is the sole explicit action for a per-style
refresh and cannot be combined with `--skip-build`. A missing or invalid
declaration fails loudly. The declaration is JSON and selects the
content-hash-stable corpus identities produced by P1K-T1:

```json
{
  "schema_version": "twinklr.style-groups.v1",
  "groups": [
    {
      "style_name": "Warm Pop",
      "selector": {"package_ids": ["<content-hash-package-id>"]}
    },
    {
      "style_name": "Sparse Drama",
      "selector": {
        "sequence_keys": ["<content-hash-package-id>/<sequence-file-id>"]
      }
    }
  ]
}
```

Selectors are an explicit union of `package_ids`, `sequence_file_ids`, and
`sequence_keys`; every group must contain at least one. The run produces one
`style_fingerprint_<style-name>.json` file per group and
`style_fingerprint_report.json`. The report flags groups with fewer than two
source sequences as `thin`; it does not disguise that low support as confidence.

```bash
uv run python scripts/demo_feature_engineering.py \
  --corpus-dir <author-local-corpus> \
  --output-dir <staged-mining-run> \
  --feature-store-db <staged-mining-run>/feature-store.sqlite \
  --style-groups <owner-style-groups.json>
```

The propensity index is refreshed once over the full content-hash-identified
corpus. A grouped output has no implicit default style: omitting `style_name`
raises with the available group names, and consumers select one explicitly with
`load_fe_artifacts(output_dir, style_name="Warm Pop")`.

## Query template retrieval

Script:
- `scripts/query_template_retrieval.py`

Example:

```bash
python scripts/query_template_retrieval.py \
  --feature-dir data/features/feature_engineering \
  --template-kind orchestration \
  --role lead \
  --top-n 15
```

Filter by effect family and flow:

```bash
python scripts/query_template_retrieval.py \
  --feature-dir data/features/feature_engineering \
  --effect-family bars \
  --min-transition-flow 0.2 \
  --top-n 20
```

## Directory Conventions

Profiles source:
- `data/profiles/<profile_dir>`

Unified corpus:
- `data/profiles/corpus/<schema_or_run_name>`

Feature outputs:
- `data/features/<run_name>`

## Notes

- `_v0_check` and `*_smoke` directories are development/test artifacts and are not canonical run paths.
- If multiple entries share the same `sequence_sha256`, feature distributions can look duplicated across package IDs.
