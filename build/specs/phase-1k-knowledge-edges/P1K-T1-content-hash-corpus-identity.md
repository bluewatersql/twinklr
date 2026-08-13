# P1K-T1 — Content-hash corpus identity

Phase: 1K · Lane: ID · Executor: opus · Verifier: opus · Depends on: —

## Objective

Replace the random-`uuid4` identity generation used across `profiling/` with
identity keys deterministically derived from content that is already hashed (and
today discarded), so that re-ingesting/re-profiling an unchanged archive produces
byte-identical primary keys on every run. This makes `feature_store`'s
`INSERT OR REPLACE` upsert semantics genuinely idempotent — the concrete mechanism
Stage 2/6 of the review named as "premise unvalidatable": today re-running
profiling over a static corpus accumulates duplicate rows rather than updating
existing ones, because content hashes are computed and then thrown away in favor
of a fresh random id at every site.

## Evidence & background

Finding **P6-M2 (MED-HIGH, ADDED at verification)**:
`profiling/pack/ingestor.py:224` generates `package_id` via `uuid4()` in the same
code region that computes `zip_sha256` — the deterministic content hash is
computed and then discarded. `profile_id` is likewise built from a uuid-derived
`package_id`, so it is not stable either. `feature_store`'s `INSERT OR REPLACE`
upsert semantics (`backends/sqlite.py:151-157` et al.) key off these identifiers
and therefore cannot deduplicate. Full finding text:
`changes/twinklr-reactivation-review/reviews/phases/corpus-intelligence.md`
("P6-M2" and "Random-UUID corpus identity defeats the store's own deduplication
intent"); corroborated in `verification.md` ("Phase 6" section) and
`reactivation-proposal.md` §2.2 item 1 ("Identity: uuid4-per-ingest defeats corpus
accumulation; content hashes computed and discarded → content-hash identity").

Four uuid4-per-run call sites (baseline `aa8d325`, re-verify line numbers before
editing):

1. `profiling/pack/ingestor.py:224` — `package_id=str(uuid.uuid4())` in
   `ingest_zip()`, same function body as `zip_sha256=sha256_file(zip_path)` two
   lines above.
2. `profiling/pack/ingestor.py:211` — `file_id=str(uuid.uuid4())` per discovered
   file in `ingest_zip()`, alongside `sha256=sha256_file(path)` on the same
   `FileEntry(...)` construction.
3. `profiling/pack/ingestor.py:174` — `file_id=str(uuid.uuid4())` for the
   XML→`.xsq`-promoted file case in `_detect_sequence_file()`, alongside
   `sha256=sha256_file(promoted_path)` on the same construction.
4. `profiling/effects/extractor.py:70` — `effect_event_id=str(uuid.uuid4())` per
   effect event in `extract_effect_events()`. A content fingerprint
   (`config_fingerprint = sha1(canonical_json(config))`, `extractor.py:16-22`) is
   already computed for each event and passed through, but not used for identity.
5. `profiling/unify.py:249` — `corpus_id=str(uuid.uuid4())` in the corpus-manifest
   writer, keyed off nothing content-derived.

`profile_id` itself is **already** deterministic — `profiler.py:233` builds it as
`f"{profile.manifest.package_id}/{profile.sequence_metadata.sequence_file_id}"`
(also documented as the composite PK in `feature_store/models.py:59`,
`ProfileRecord.profile_id`). Once `package_id` (site 1) is content-derived,
`profile_id` becomes deterministic automatically — do not touch `profiler.py:233`.

Several downstream ids are *already* deterministic `uuid5` derivations seeded by
these upstream random values (`feature_engineering/phrase_encoder.py:547`,
`motifs.py:121,289`, `stack_detector.py:198`, `taxonomy/target_roles.py:198`,
`templates/miner.py:233,427`) — fixing the four upstream sites makes all of these
deterministic as a side effect. **Do not modify these `uuid5` call sites** — they
are correct today; they are only non-deterministic because their inputs are.

**Feature store version gate** (`feature_store/backends/sqlite.py:84-117`):
`SQLiteFeatureStore.initialize()` raises `FeatureStoreSchemaError` when the
stored schema version does not match the configured one, and there is **no
migration runner** — `SchemaBootstrapper.needs_migration()`
(`bootstrap/schema.py:100-109`) exists as a query but nothing acts on its answer.
This is a verified, deliberate design gap (P6 review, "Feature-store schema
design" section): "a schema bump requires manually deleting/recreating the DB."
This task does not change the DDL/schema tables at all — it changes the *values*
written into existing key columns — so the version gate will **not** catch a
mixed old-uuid/new-hash database automatically.

## Current behavior

`ingest_zip()`, `_detect_sequence_file()`, `extract_effect_events()`, and the
corpus-manifest writer in `unify.py` all mint a fresh `uuid.uuid4()` per run for
`package_id`, `file_id` (both sites), `effect_event_id`, and `corpus_id`
respectively, immediately after or alongside computing a SHA-256/SHA-1 content
hash of the same data that is discarded for identity purposes. Re-running the
same ingest/profile/extract/unify pipeline over byte-identical input produces a
completely different set of primary keys every time.

## Target behavior

All five call sites produce identity values derived deterministically from
content, per this fixed key-shape decision (do not relitigate):

- **`package_id`** = `zip_sha256[:16]` — the first 16 hex characters (64 bits) of
  the already-computed `sha256_file(zip_path)` digest. Prefixed, not full-length:
  `package_id` appears in many downstream composite strings
  (`profile_id`, log lines, `uuid5` namespaces) where a 64-bit prefix is ample
  collision resistance for a single-developer corpus and keeps those composites
  shorter.
- **`file_id`** = the file's own full SHA-256 hex digest, i.e. reuse the
  `sha256_file(path)` value already computed for `FileEntry.sha256` verbatim as
  `FileEntry.file_id` (both fields end up equal — content-addressed). Two files
  with byte-identical content intentionally receive the same `file_id`; this is
  correct content-addressing, not a bug — they *are* the same content.
- **`profile_id`** — unchanged formula (`{package_id}/{sequence_file_id}`,
  `profiler.py:233`); becomes deterministic automatically once `package_id` is.
- **`effect_event_id`** = `uuid5(NAMESPACE, key)` where `NAMESPACE` is a new
  module-level constant (`uuid.uuid5(uuid.NAMESPACE_URL, "twinklr.profiling.effect_event")`,
  computed once) and
  `key = f"{package_id}:{sequence_file_id}:{start_ms}:{end_ms}:{layer_name}:{target_name}:{effect_type}:{config_fingerprint}:{dup_index}"`.
  `dup_index` is a 0-based counter of how many prior events in the same
  `extract_effect_events()` call produced an identical key *before* appending
  `dup_index` — this disambiguates the rare case of two genuinely distinct effect
  instances sharing identical start/end/layer/target/type/config (append-order
  stable since `events` is already iterated in a fixed nested-loop order).
- **`corpus_id`** = `"corpus:" + sha256(canonical_json({"profile_dirs": sorted(str(p) for p in profile_dirs), "schema_version": schema_version, "manifest_schema_version": CORPUS_MANIFEST_SCHEMA_VERSION}))[:16]`.
  Reuse the existing `_canonical_json`-style helper pattern from
  `effects/extractor.py:16-18` (sorted-keys, compact separators) rather than
  inventing a new serialization. Re-running `unify()` over the same set of
  `profile_dirs` (unchanged corpus) yields the same `corpus_id`; adding/removing a
  profile directory changes it.

Re-ingesting, re-profiling, re-extracting, or re-unifying the same unchanged
input therefore produces identical primary keys end to end, and
`feature_store.upsert_profile()`/`upsert_corpus_metadata()`/etc. genuinely
overwrite rather than duplicate.

**Non-goals** (explicit, do not implement):

- No migration runner for `feature_store` — out of scope by design; the existing
  fail-loud version-mismatch behavior stands.
- No change to `feature_store` schema DDL/tables — this is a value-convention
  change only.
- No change to `profile_id`'s formula.
- No change to any existing `uuid5`-based downstream derivation
  (`phrase_encoder.py`, `motifs.py`, `stack_detector.py`, `target_roles.py`,
  `templates/miner.py`) — they inherit determinism for free once their inputs are
  fixed.

**Local-store recreate note (must ship as a doc/log, not code):** because this is
a value-convention change with no DDL change, the version gate provides **no**
automatic protection against a mixed old-uuid/new-hash local SQLite file. Any
existing local `feature_store` database built before this change must be deleted
and rebuilt from a fresh ingest/profile run — add a short note to this effect in
`feature_store/README.md` if one exists, or as a docstring on
`SQLiteFeatureStore.initialize()`; do not attempt to write a migration for it.

## Implementation approach

Files to touch:

- `packages/twinklr/core/profiling/pack/ingestor.py` — `ingest_zip()` (site 1, 2),
  `_detect_sequence_file()` (site 3).
- `packages/twinklr/core/profiling/effects/extractor.py` — `extract_effect_events()`
  (site 4); reuse its existing `_canonical_json`/`_config_fingerprint` helpers,
  do not duplicate them.
- `packages/twinklr/core/profiling/unify.py` — corpus-manifest writer (site 5,
  around line 249); reuse the same canonical-json approach.
- New shared helper recommended (not mandatory): a small
  `profiling/identity.py` module holding a `content_uuid5(namespace_key: str) -> str`
  or similar, if it avoids duplicating the canonical-json logic across
  `extractor.py` and `unify.py`. Keep it minimal — this is a value-derivation
  change, not a new subsystem.
- Remove the now-unused `import uuid` from `ingestor.py` only if no other uuid
  use remains in that file after the change (`_detect_sequence_file` currently
  imports `uuid` at module level shared with `ingest_zip`; verify before
  removing).

Sequencing constraints inherited from `build/plan/00-overview.md` that touch
this task: none apply directly (T1 is not named in any of the six
cross-cutting sequencing bullets), but T1 is itself a **prerequisite for P1K-T2**
("Lane AL (labels): T2 ... after T1 (stable IDs)") — land T1 first within Phase
1K.

## Acceptance criteria

- Ingesting the same zip archive twice (no bytes changed) produces an identical
  `package_id` and an identical `file_id` for every entry, in both runs.
- Ingesting a zip archive that differs by even one byte produces a different
  `package_id`.
- Two files with byte-identical content (anywhere in the same or different
  archives) produce the same `file_id`.
- Extracting effect events from the same `XSequence` twice produces an identical
  ordered tuple of `effect_event_id`s.
- Two distinct effect instances that share identical
  `(start_ms, end_ms, layer_name, target_name, effect_type, config_fingerprint)`
  receive distinct `effect_event_id`s (via the `dup_index` disambiguator).
- Running `unify()` twice over an unchanged set of profile directories produces
  an identical `corpus_id`; changing the profile-directory set changes it.
- `profile_id` continues to equal `f"{package_id}/{sequence_file_id}"` and is
  therefore deterministic as a consequence, with zero changes to `profiler.py`.
- `upsert_profile()` called twice with `ProfileRecord`s built from two identical
  re-ingest/re-profile runs results in exactly one row in the `profiles` table
  (row count via `get_corpus_stats().profile_count` or a direct query), not two.
- No `uuid5` call site outside the five listed above is modified.
- `mypy`/`ruff` clean on all touched files.

## Tests

New/changed tests (TDD: write the idempotency assertions first, watch them fail
against current `uuid4` behavior, then implement):

- `tests/unit/profiling/test_ingestor.py`: add
  `test_ingest_zip_is_idempotent_on_unchanged_archive` (re-ingest same fixture
  zip twice, assert `manifest.package_id` and every `FileEntry.file_id` match
  across runs) and `test_ingest_zip_changes_id_on_content_change` (mutate one
  byte in a temp copy, assert `package_id` differs) and
  `test_duplicate_content_files_share_file_id` (two files with identical bytes
  under different names get the same `file_id`).
- `tests/unit/profiling/test_extractor.py` (or wherever
  `extract_effect_events` is currently tested): add
  `test_effect_event_id_is_deterministic` (extract twice from the same
  `XSequence`, assert identical `effect_event_id` tuples) and
  `test_duplicate_effect_signature_gets_distinct_ids` (construct two effects
  with identical start/end/layer/target/type/config, assert their
  `effect_event_id`s differ).
- `tests/unit/profiling/test_unify.py` (or corpus manifest test module): add
  `test_corpus_id_stable_across_unchanged_profile_set` and
  `test_corpus_id_changes_with_profile_set`.
- `tests/integration/profiling/` or `tests/unit/feature_store/`: add an
  idempotency round-trip test — build two `ProfileRecord`s from two identical
  re-ingest/re-profile passes over the same fixture, `upsert_profile()` both,
  assert the store contains exactly one row for that `profile_id`.

## Verification commands

```bash
uv run pytest tests/unit/profiling/test_ingestor.py tests/unit/profiling/test_extractor.py tests/unit/profiling/test_unify.py -q
uv run pytest tests/unit/feature_store/ -q
uv run ruff check packages/twinklr/core/profiling
uv run mypy packages/twinklr/core/profiling
```

No LOCAL-ONLY / paid-API steps — this task touches no LLM call sites and
requires no live xLights GUI.

## Effort & risk

**M.** Touches four small, well-isolated functions plus one shared corpus
manifest writer; the main risk is under-specifying the `effect_event_id`
disambiguation (silently colliding two genuinely distinct effects) — mitigated
by the `dup_index` counter and its dedicated test. Secondary risk: an executor
mistakes this for a schema-migration task and starts building a migration
runner — the "recreate, not migrate" note above is written to head that off
explicitly; if the executor is unsure, they should re-read the "Local-store
recreate note" and stop rather than add migration machinery.
