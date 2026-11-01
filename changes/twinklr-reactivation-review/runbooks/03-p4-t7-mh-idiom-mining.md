---
type: change
status: active
area: engineering
created: 2026-11-01
updated: 2026-11-01
---

# Runbook 03 — P4-T7 moving-head idiom-mining feasibility (optional, corpus-gated)

**Purpose:** let the owner re-enter P4-T7 and run its capped, offline feasibility
investigation, ending in a go/no-go decision memo.

**Read this first.** P4-T7 is an *optional, capped feasibility investigation*. It is not
product work, it ships no code, and finishing (or skipping) it is **not** automatic Phase 4
completion. Phase 4 stays 6/7 and P4-T7 stays NO-GO/deferred until Part A passes. The only
strict Phase 4 exit blocker is the Ollama smoke
([runbook 01](01-ollama-cloud-smoke.md)), not this task. An "inconclusive" memo is a valid,
acceptable result.

Authoritative sources (the spec wins over this runbook if they disagree):
[P4-T7 spec](../build/specs/phase-4-compounding/P4-T7-mh-idiom-mining-exploration.md),
[repository preflight](../build/specs/phase-4-compounding/P4-T7-repository-preflight.md)
(note the spec's "Superseding P2K re-entry clarification": artifact 4 is the strict
`OWNER_DECISIONS.json` with exactly eight entries, not a five-entry log),
[Phase 4 plan](../build/plan/07-phase-4-compounding.md),
[HANDOFF blockers #2 and #3](../build/plan/HANDOFF.md),
[feature-engineering workflow](../../../scripts/docs/feature_engineering.md).

Run every command from the repo root (`/Users/ondeck/work/github/twinklr`). Use
`.venv/bin/python` (or `uv run python` when online). **Nothing in this runbook calls a
network, provider, xLights, or audio service**; if a step seems to need one, stop (see
Stop conditions).

---

## Part A — Admission gate (no corpus parsing)

All of the following must hold, or P4-T7 stays NO-GO and you stop here.

| # | Precondition | Evidence |
|---|---|---|
| A1 | P2K-T2 empirical exits accepted (real-corpus run, unchanged rerun, non-empty distributions, eight owner decisions) | `<staged-mining-run>/quality_gate_evidence_manifest.json` with `accepted: true` |
| A2 | Private MH corpus manifest exists, is valid, and the owner declared it `sufficient` | `mh-corpus-evidence.json` from the validator |
| A3 | Both bound together | The validator hashes the exact P2K evidence file into the MH evidence |

The preflight's "five re-entry artifacts" map as: artifacts 1-4 are the P2K-T2 outputs
(real-corpus run manifest, idempotent-rerun record, non-empty distribution report, owner
decisions) produced by [runbook 02](02-phase-2k-catalog-growth.md); artifact 5 is the MH
manifest below.

### A1. Accepted P2K-T2 evidence

Complete runbook 02 first. Its result is the staged run directory containing
`quality_gate_evidence_manifest.json`, written by
`scripts/report_quality_gate_distributions.py --run-dir <dir> --bind-owner-decisions
--accepted-on YYYY-MM-DD`. Quick check:

```bash
export P2K_RUN=<absolute path of the staged P2K-T2 mining run dir>
test -f "$P2K_RUN/quality_gate_evidence_manifest.json" && echo "A1 file present" || echo "A1 MISSING - stop"
```

The validator in A2 enforces `accepted == true` itself and rejects the run otherwise.

### A2. Private MH corpus manifest

#### Inputs you must supply

1. **Corpus files**, owner-local, outside the repo or under gitignored `data/` (the
   validator rejects a manifest inside the repo that is tracked or not gitignored).
   Suggested layout (any absolute paths work; the archive must stay read-only source):

   ```text
   ~/twinklr-private/mh-corpus/<vendor>/<pack>.zip        # or .xsqz
   ~/twinklr-private/mh-corpus/<vendor>/<pack>/<seq>.xsq  # the extracted sequence file
   ~/twinklr-private/mh-corpus/manifest.json              # private manifest
   ```

   `sequence_path` must point at an actual file on disk (extract the `.xsq` yourself, e.g.
   `unzip` into a directory next to the archive; do not extract into a profiler scratch
   area). Never commit any of this, never redistribute vendor content.
2. **Manifest** `twinklr.mh-corpus-manifest.v1` (schema from
   `packages/twinklr/core/feature_engineering/mh_corpus_manifest.py`; strict, unknown
   fields rejected). Hash each file first:

   ```bash
   shasum -a 256 <archive> <sequence.xsq>
   ```

   ```json
   {
     "schema_version": "twinklr.mh-corpus-manifest.v1",
     "corpus_id": "<owner-local-id>",
     "created_at_utc": "2026-11-01T00:00:00Z",
     "entries": [{
       "package_id": "<stable package id>",
       "sequence_file_id": "<stable sequence id>",
       "vendor": "<source vendor>",
       "source_kind": "owner_local_vendor_archive",
       "archive_path": "/absolute/path/pack.zip",
       "archive_sha256": "<64 hex>",
       "sequence_path": "/absolute/path/seq.xsq",
       "sequence_sha256": "<64 hex>",
       "fixture_families": ["<family>"],
       "fixture_roles": ["<role>"]
     }],
     "sufficiency": {
       "decision": "sufficient",
       "declared_by": "<owner>",
       "declared_at_utc": "2026-11-01T00:00:00Z",
       "minimum_sequences": 5,
       "minimum_vendors": 2,
       "minimum_fixture_families": 2,
       "minimum_fixture_roles": 2,
       "rationale": "<why this is enough for the capped spike>"
     }
   }
   ```

   Both timestamps must be timezone-aware UTC. Logical identity
   `(package_id, sequence_file_id)` and `sequence_sha256` must be unique across entries.
3. **What "sufficient" means.** The spec does not fix numbers; the *owner* declares the
   minima in `sufficiency` and the validator enforces them (and refuses a `sufficient`
   declaration the corpus cannot meet). To be useful for the investigation in Part B the
   minima above are a recommended floor, taken from the preflight's sample rules: at least
   3 sequences from at least 2 independently hashed packs and at least 2 distinct DMX
   fixture/layout profiles are needed or Part B stops. Choose minima that guarantee that
   (the suggested `5 / 2 / 2 / 2` does, assuming each pack contains DMX moving-head
   targets). Do not lower them to pass.

#### Validate

```bash
.venv/bin/python scripts/validate_mh_corpus_manifest.py \
  --manifest ~/twinklr-private/mh-corpus/manifest.json \
  --p2k-evidence "$P2K_RUN/quality_gate_evidence_manifest.json" \
  --evidence-out ~/twinklr-private/mh-corpus/mh-corpus-evidence.json \
  --require-sufficient
```

Verified flags: `--manifest`, `--p2k-evidence`, `--evidence-out` (all required),
`--require-sufficient`. Exit `0` + JSON printed = pass; exit `2` + `MH corpus manifest
rejected: ...` on stderr = fail (fix the stated cause; do not edit minima downward to
force a pass). It checks file existence and SHA-256 of every archive and sequence,
duplicates, P2K acceptance, and owner minima, **without parsing sequence content**. The
redacted evidence (`twinklr.mh-corpus-evidence.v2`) binds the manifest hash and the exact
P2K evidence hash and omits paths/vendors/rationale text. It may be quoted in the memo.

### A3. Admission decision

If A1 and A2 both passed, record admission in the scratch notes (date, both evidence
hashes) and continue. If either fails: P4-T7 stays NO-GO. Record nothing else; there is no
verdict to write. (Optionally append a dated one-line "still NO-GO, reason" to the P4-T7
spec execution status in a docs commit.)

---

## Part B — Capped offline investigation

**Hard caps:** 165 minutes of analysis, absolute stop at 180 minutes (the last 15 are
packaging only), local-only, offline, zero paid/live calls, zero application-code changes,
at most 5 sequences. Start a visible timer now and note the start time.

```bash
export P4T7_START="$(date -u +%FT%TZ)"; echo "$P4T7_START"
```

### B1 (0-15 min) Re-verify admission and boundaries

Re-run the A2 validator (idempotent) and confirm `git status --short` is clean of anything
you did not intend. Confirm the memo target path does not exist yet.

### B2 (15-35 min) Select the sample and build the isolated scratch root

The profiler's ingest step deletes and recreates a sibling `<archive_stem>_extracted`
directory next to whatever archive it is given (`ingest_zip` in
`profiling/pack/ingestor.py`). **Never pass an owner archive path to the profiler.** Always
work on hash-verified copies inside a brand-new scratch directory.

1. Pick at most 5 manifest entries: at least 3 sequences, from at least 2 independently
   hashed packs, covering at least 2 distinct DMX fixture/layout profiles (by manifest
   `fixture_families`). Fewer than that: **stop** (Stop conditions).
2. Create the scratch root and copy (this directory must be new and empty):

   ```bash
   export P4T7_SCRATCH="$(mktemp -d "${TMPDIR:-/tmp}/p4t7-scratch.XXXXXX")"
   cp ~/twinklr-private/mh-corpus/<vendor>/<pack>.zip "$P4T7_SCRATCH/"
   # repeat per selected archive
   ```

3. Verify every copy against the manifest source hash; they must match exactly:

   ```bash
   shasum -a 256 ~/twinklr-private/mh-corpus/<vendor>/<pack>.zip "$P4T7_SCRATCH/<pack>.zip"
   ```

4. Record a sample table (source path, copy path, `archive_sha256`, `sequence_sha256`)
   in scratch notes only (`$P4T7_SCRATCH/notes.md`), never in Git.

### B3 (35-80 min) Run the existing profiler on the copies only

`scripts/demo_profiling.py` (verified flags: `--input`, `--output-dir`,
`--feature-store-db`, `--force`) wraps `SequencePackProfiler`. Run one archive at a time,
with output inside the scratch root. Omit `--feature-store-db` (an in-memory null store is
used, so no persistent store is touched):

```bash
.venv/bin/python scripts/demo_profiling.py \
  --input "$P4T7_SCRATCH/<pack>.zip" \
  --output-dir "$P4T7_SCRATCH/profile_<pack>" \
  --force
```

It prints a one-row table (`status`, `song`, `events`, `models`, `groups`, ...). Do **not**
run it with no `--input` (it falls back to default `data/vendor_packages` inputs and
default `data/profiles` outputs, outside the scratch root).

After each run confirm the `<pack>_extracted` directory exists under `$P4T7_SCRATCH` and
nothing was created beside the owner's original archive:

```bash
ls "$P4T7_SCRATCH"
ls ~/twinklr-private/mh-corpus/<vendor>/   # must be unchanged
```

Record per sequence: parse status, event count, model count, whether a companion
`xlights_rgbeffects.xml` layout was present, and whether any DMX fixture was detected.
Copy no raw payload into the repo.

### B4 (80-125 min) Trace what survives: the seam/wall table

This step has **no tooling**; it is analyst work in scratch. For each of the (at most) 5
sequences, inspect the profile artifacts written to `$P4T7_SCRATCH/profile_<pack>/` (JSON
files such as the layout profile and event records; list the directory and open them with
`jq`/`less`; exact artifact names were not verified because no real profile was produced
in this runbook's authoring) and fill a table of fields **retained vs. lost** for the
idioms the spec cares about:

- Does the layout profile carry a `DmxFixtureProfile` (channel count, node names,
  color-wheel entries, pan/tilt motor metadata) for the moving heads?
- Do event records preserve the EffectDB settings (raw string and parsed params) and do
  those include distinguishable DMX channel values (pan/tilt/dimmer/color/shutter/gobo)?
- Per the preflight, expected walls to confirm or refute with evidence: fixture topology
  dropped before feature encoding (`enrich_events` -> `EnrichedEventRecord`/`EffectPhrase`);
  `PhraseEncoder` collapses `DMX`/`MovingHead` to coarse `dmx_program` classes; the
  display stack detector (`EffectStackDetector`) does not reconstruct multi-fixture
  movement/phase; `PropensityMiner`/`TemplateMiner` outputs do not match the moving-head
  `TemplateDoc` contract (`moving_heads/templates/`). Cite exact symbols and the fields
  you actually observed.
- Optionally, if time allows and still offline, reason (read code, do not run mining)
  about whether `feature_engineering.alignment.TemporalAlignmentEngine` and the phrase/stack
  pipeline could consume MH events through an adapter.

Do not modify product code. Do not keep a prototype in the tree; scratch exploration stays
under `$P4T7_SCRATCH`. If a script is genuinely worth preserving, name it in the memo as
spike-quality and attach it only if the owner decides so.

### B5 (125-165 min) Draft the decision memo

See Part D. Answer all five questions from the spec's Target behavior:

1. Do MH sequences exist in the corpus in sufficient quantity/variety? (Re-verified from
   the manifest and B3, not from the plan's old "deleted-history artifact" claim, which
   the preflight refuted: the only deleted `.xsq` is the owner's own show, not a vendor
   pack.)
2. Can the existing propensity/taxonomy/stack mining be pointed at MH data with a
   reasonable adapter, or is a different extraction needed? (Cite code and MH structures.)
3. If feasible, the rough shape and size of the work versus P2K-T2/T3/T4.
4. If not, why, and what would have to change to revisit.
5. Recommendation: pursue now, pursue later with named triggers, or do not pursue.
   An explicit "inconclusive; here is what is missing" counts.

### B6 (165-180 min) Administrative packaging only

No new parsing, archives, or analysis. Collect the evidence hashes and finish the
checklist in Part E. **Hard stop at minute 180.**

### Cleanup

When the memo is committed (or the investigation is abandoned), delete the scratch root.
Only delete the exact directory you created; check the path first:

```bash
echo "$P4T7_SCRATCH"          # confirm it is the mktemp dir, not a corpus dir
rm -r "$P4T7_SCRATCH"
```

---

## Stop conditions (record the named reason, write an "inconclusive" memo, end)

Stop immediately if any of these occur:

- any admission artifact is missing, stale, inaccessible, or hash-inconsistent;
- a scratch root cannot be created, a source/copy hash differs, a profiler input resolves
  outside the scratch root, or a generated `_extracted` directory would;
- the sample has fewer than 3 sequences, fewer than 2 independently hashed packs, or
  fewer than 2 distinct DMX fixture/layout profiles;
- fewer than 2 sampled sequences join parsed effects to a `DmxFixtureProfile`;
- the existing parser/EffectDB path yields no distinguishable DMX channel signal in the
  first two qualified sequences;
- continuing needs network/provider access, xLights, audio playback/analysis,
  redistribution of raw vendor data, or changes to tracked application code;
- scratch work would have to become a retained application prototype;
- elapsed time reaches 165 minutes (stop analysis) or 180 minutes (absolute).

## Cost and scope caps (from the spec)

- Time: 165 min analysis / 180 min absolute; "S, one focused working session".
- Cost: zero. No paid or live call of any kind is part of this task.
- Scope: a memo. No MH-mining code, no MH template changes, no display-pipeline changes;
  `git diff --stat main` must show only the memo (plus an explicitly labeled prototype if
  the owner chooses to keep one).
- Data: local only; no redistribution of vendor-derived content.

---

## Part D — Recording the verdict

Write one decision memo in one of the two canonical homes (spec "Deliverable"; choose per
`AGENTS.md` knowledge placement):

- recommended: `changes/mh-idiom-mining-feasibility/memo.md` (short-lived change dir;
  start from [templates/change.md](../../../templates/change.md) and add the dir to
  [changes/ACTIVE.md](../../ACTIVE.md) while open), **or**
- `memories/decisions/mh-idiom-mining-<verdict>.md` (start from
  [templates/memory.md](../../../templates/memory.md); update
  [memories/INDEX.md](../../../memories/INDEX.md)).

The memo must contain: the five answers with cited evidence (paths, symbols, observed
fields, or "could not verify, because ..."); the recommendation; the evidence hashes
(MH manifest hash, MH evidence hash, P2K evidence hash, sample source/copy hashes, no
paths or vendor names if the memo is committed); elapsed time and stop reason if any.
Then update the P4-T7 row/status in the Phase 4 plan and
[HANDOFF.md](../build/plan/HANDOFF.md) (docs-only commit). Commit the memo and doc
updates, then run `make validate` before claiming done. It refuses a dirty tree
(AGENTS.md definition of done).

## Part E — Final evidence checklist

- [ ] A1: accepted P2K-T2 `quality_gate_evidence_manifest.json` present (runbook 02 done)
- [ ] A2: `validate_mh_corpus_manifest.py ... --require-sufficient` exited 0;
      `mh-corpus-evidence.json` saved; its hashes recorded
- [ ] B2: sample table with matching source/copy SHA-256s; scratch root was new
- [ ] B3: profiler run only on scratch copies; owner originals/dirs unchanged
- [ ] B4: retained-vs-lost field table with exact symbols/fields
- [ ] Elapsed time recorded and under 165 min analysis / 180 min absolute
- [ ] Memo written in `changes/mh-idiom-mining-feasibility/` or `memories/decisions/`,
      answering all five questions with a clear recommendation (or named inconclusive)
- [ ] `git diff --stat main` shows no application-code changes
- [ ] No private manifest, corpus, archive, hash-of-paths, or scratch output committed
- [ ] INDEX/ACTIVE, Phase 4 plan row, and HANDOFF updated; `make validate` output saved
- [ ] Scratch root removed

## What is missing (honest tooling gaps)

- No tool builds the MH manifest; it is hand-authored JSON with hand-computed hashes.
- The v1 manifest schema has no fields for xLights version, companion-layout hash, or
  detected DMX target names/types, all of which preflight artifact 5 asks for. Record
  them in the scratch sample table / memo until the schema is extended (a code change out
  of scope for this task).
- No tool creates/verifies the isolated scratch copies (use `mktemp`, `cp`, `shasum`).
- No tool checks the stop criteria "two sequences join effects to a `DmxFixtureProfile`" or
  "distinguishable DMX channel signal"; B4 is manual inspection.
- No MH adapter, MH feature extractor, or MH taxonomy exists. By design none may be built
  here; the memo sizes that work instead.
