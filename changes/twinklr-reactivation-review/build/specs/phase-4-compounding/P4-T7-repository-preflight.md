# P4-T7 — Repository-only preflight

- Date: 2026-08-26
- Base: `63293f608b3c0564297a140f87e10b44df547163`
- Scope: tracked source, tests, specifications, and Git history only

## Result boundary

This is a safe prerequisite audit, not P4-T7 execution. It accessed no corpus content,
vendor archive, network, provider, xLights process, audio, or application prototype. It
does not decide whether moving-head idiom mining is feasible or worth building.

## History premise correction

Repository history does **not** prove that vendor-authored moving-head sequences exist.

- Commit `b6fdfd224b544bee3e01fe9cbf41468eac018286` added
  `artifacts/need_a_favor/need_a_favor_blinkb0t_mh.xsq` alongside the project's own
  fixture configuration and planning checkpoints. Existing review evidence in
  `reviews/product-and-approach.md` classifies it as the author's own real-rig show; the
  tracked path and adjacent filenames provide no vendor provenance. This preflight did
  not open the raw `.xsq` and makes no claim about uninspected internal metadata.
- Commit `794a8bb2b819e530a1dda27f2b83d92f373dee6a` deleted that file.
- An all-history deleted-file query over `*.xsq`, `*.xsqz`, and `*.zip` returns only that
  one `.xsq`. No deleted vendor archive or moving-head corpus manifest was found.
- Commit `82aaf382a1710f1d907f82ac791443ba5b54a16e` deleted
  `scripts/build_profile_corpus.py`; a deleted corpus-building script is not evidence
  that a qualifying corpus was present.

The active question therefore starts with owner-supplied, hash-pinned corpus evidence.
It may not use the old "deleted-history artifact proves they exist" sentence as input.

## Reusable repository seams

These are code-shape observations, not evidence that the seams work on an MH corpus.

| Seam | Reusable behavior | Evidence |
|---|---|---|
| Archive discovery and identity | Recursively finds `.zip`/`.xsqz` files under vendor namespaces; ingestion produces content hashes and a package manifest with zip-slip checks. | `profiling.discovery.discover_vendor_archives`; `profiling.pack.ingestor.ingest_zip` |
| Generic sequence parsing | Parses non-timing xLights elements, layers, effect timing/type, attributes, EffectDB references, and raw palette data without filtering by display model category. | `formats.xlights.sequence.parser.XSQParser`; `profiling.effects.extractor.extract_effect_events` |
| Structured EffectDB preservation | Retains the raw settings string and parses namespaced parameters into typed values while preserving partial/failure status. | `profiling.effects.effectdb_parser.parse_effectdb_settings`; `profiling.models.events.EffectEventRecord` |
| DMX layout recognition | Recognizes xLights DMX fixture types and can profile channel count, node names, color-wheel entries, and pan/tilt motor metadata when a companion RGB-effects layout exists. | `profiling.layout.classifier.DMX_MODEL_TYPES`; `profiling.layout.profiler._extract_dmx_profile`; `profiling.models.layout.DmxFixtureProfile` |
| Stable event-to-corpus plumbing | Content-addressed package/sequence/event identities, timing alignment, phrase records, and target-local temporal grouping already exist. | `profiling.identity`; `feature_engineering.alignment.TemporalAlignmentEngine`; `feature_engineering.phrase_encoder.PhraseEncoder`; `feature_engineering.stack_detector.EffectStackDetector` |

## Structural walls visible without corpus access

| Wall | Why the current seam is insufficient |
|---|---|
| Archive names do not establish content | Discovery recognizes extensions and vendor directories; it does not prove an archive contains DMX moving-head targets or usable layout metadata. |
| Fixture topology is dropped before feature encoding | `LayoutProfiler` can construct `DmxFixtureProfile`, but `enrich_events` carries only coarse target category/tags/pixel fields. Pan/tilt motors, node names, channel count, and color-wheel data do not reach `EnrichedEventRecord` or `EffectPhrase`. |
| DMX behavior is collapsed | `PhraseEncoder` maps `DMX` and `MovingHead` to coarse `dmx_program` classes. It preserves generic EffectDB parameters but has no decoder that normalizes them into pan, tilt, dimmer, color, shutter, and gobo trajectories. |
| Display stack semantics are not MH idioms | `EffectStackDetector` groups overlapping layers on one target and assigns display-oriented BASE/RHYTHM/ACCENT roles. It does not reconstruct coordinated multi-fixture movement, phase, geometry, or channel transitions. |
| Existing outputs do not match the MH template contract | `PropensityMiner` counts effect-family to target-name-derived model-type affinity, and `TemplateMiner` emits display phrase/stack signatures. The moving-head renderer consumes `TemplateDoc` steps with geometry, movement, timing, dimmer, color, shutter, gobo, presets, and fixture-role semantics. No adapter joins those representations. |

## Exact five re-entry artifacts

P4-T7 full execution may be reconsidered only when all five artifacts are accessible and
their hashes/paths agree. Tool availability alone does not substitute for any artifact.

1. **`P2K-T2-real-corpus-run-manifest`** — accepted manifest naming the owner-local
   corpus roots, package/sequence content hashes, profiler/parser versions, staged output
   paths, and zero live-catalog mutation.
2. **`P2K-T2-idempotent-rerun-record`** — before/after store counts and corpus hashes
   proving an unchanged second run creates no duplicate identities or rows.
3. **`P2K-T2-nonempty-distribution-report`** — real, non-zero distributions across
   every mined candidate for `support_count`, `cross_pack_stability`, and
   `distinct_pack_count`; the `effective_min_support` and `effective_min_stability`
   actually applied by adaptive promotion; and pass/fail sensitivity at each configured
   value plus at least two nearby values for every numeric threshold/cap in P2K-T2's
   five named review line items: (1) configured promotion support/stability, (2)
   `PromotionPipeline.run()`'s hardcoded support/stability defaults, (3) propensity
   minimum support/anti-affinity, (4) the target-role score cutoff, and (5) the
   per-family/per-cluster caps. It must explicitly preserve for owner resolution the
   `promotion.py` defaults (`5`/`0.3`) versus `config.py` configured values
   (`2`/`0.015`) discrepancy rather than silently reconciling it.
4. **`P2K-T2-owner-threshold-decision-log`** — five dated owner-authored keep/change/
   defer entries required by P2K-T2, with any accepted code change separately landed.
5. **`P4-T7-MH-corpus-manifest`** — provenance-bearing inventory of the proposed MH
   subset: immutable archive and sequence hashes, source/vendor namespace, xLights
   version, companion layout hash, detected DMX target names/types, and explicit local
   access path. It must contain no redistributed raw vendor content.

## Future offline session: 165-minute plan, 180-minute absolute cap

This plan is dormant until all five re-entry artifacts pass preflight. It authorizes no
future action by itself.

`SequencePackProfiler` delegates to `ingest_zip`, which creates—and deletes if already
present—a sibling `<archive_stem>_extracted` directory. Therefore an owner archive must
never be profiled in place. Before any profiler/parser call, each selected archive must
be copied into a newly created, task-owned isolated scratch root, and the source and copy
SHA-256 values must match. Only the verified scratch copy may be passed to the profiler;
its sibling extraction directory must also resolve inside that same scratch root.

| Elapsed | Work | Required output |
|---|---|---|
| 0–15 min | Verify the five artifacts, hashes, local-only scope, and scratch output boundary. | Admission checklist or immediate stop record. |
| 15–35 min | Use the MH manifest—not filename guesses—to select at most five sequences. Require at least three sequences from two independently hashed packs and at least two distinct DMX fixture/layout profiles. Copy only the selected archives into a newly created task-owned isolated scratch root, then hash-verify every copy against its manifest-qualified source. | Hash-pinned source/copy sample table and scratch-root boundary. |
| 35–80 min | Run existing profiler/parser entrypoints offline only against the hash-verified scratch copies. Confirm each generated `<archive_stem>_extracted` sibling resolves inside the task-owned scratch root; write every other output there as well. | Per-sequence parse status and counts, with no raw payload copied into Git. |
| 80–125 min | Trace whether extracted records retain enough channel/layout meaning to express one candidate idiom shape. Analysis stays in scratch/notebook notes; do not modify product code or keep a prototype. | Seam/wall evidence table with exact fields lost or retained. |
| 125–165 min | Draft the P4-T7 decision memo against all five target questions, including an inconclusive result when required. | Reviewable memo plus evidence hashes. |
| 165–180 min | Administrative evidence packaging only. No new archive, parse, adapter, or analysis work may start. | Hard stop by minute 180. |

## Mandatory stop criteria

Stop and record the named reason immediately if any condition occurs:

- any re-entry artifact is missing, stale, inaccessible, or hash-inconsistent;
- task-owned isolated scratch storage cannot be provisioned, a source/copy hash differs,
  a profiler input resolves outside that scratch root, or a generated sibling extraction
  directory would resolve outside it;
- the manifest-qualified sample has fewer than three sequences, fewer than two
  independently hashed packs, or fewer than two distinct DMX fixture/layout profiles;
- fewer than two sampled sequences join parsed effects to a `DmxFixtureProfile`;
- the existing parser/EffectDB path yields no distinguishable DMX channel signal in the
  first two qualified sequences;
- continuing requires network/provider access, xLights, audio playback/analysis,
  redistribution of raw vendor data, or modification of tracked application code;
- scratch work would need to become a retained application prototype;
- elapsed time reaches 165 minutes (analysis stop) or 180 minutes (absolute stop).

Each stop outcome may support an "inconclusive—named prerequisite missing" memo. None of
these repository-only observations supports a feasibility verdict now.

## Repository evidence commands

```bash
git log --all --diff-filter=D --name-only -- '*.xsq' '*.xsqz' '*.zip'
git log --all --name-status -- artifacts/need_a_favor/need_a_favor_blinkb0t_mh.xsq
git show --stat --summary b6fdfd2
git show --stat --summary 82aaf38
```
