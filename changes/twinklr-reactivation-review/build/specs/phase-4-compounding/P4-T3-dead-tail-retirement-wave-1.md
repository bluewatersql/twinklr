# P4-T3 — Dead-tail retirement wave 1 (safe)

Phase: 4-compounding · Lane: dead-tail (touches many files across
`packages/twinklr/core/` — see per-item file lists below; expect broad but shallow
diffs) · Executor: sonnet · Verifier: opus · Depends on: Phases 1P/3 merged (per
`changes/twinklr-reactivation-review/build/plan/07-phase-4-compounding.md` task table)

## Objective

Delete every item in this task's inventory that has verified zero production callers,
in the sequencing order this spec specifies, without breaking the build or dropping
test coverage that has no other home. Diarization is explicitly OUT of this task's
scope — it is deleted in P4-T1, ahead of the pyannote-audio 4.x bump, per the plan's
sequencing note.

## Evidence & background

This spec exists specifically because prior review passes contained wrong deletion
labels that a naive executor would act on verbatim. **Two rows were adversarially
verified and REJECTED as not-deletable-as-is** (`curves/modifiers.py`,
`curves/providers/native.py` — see item 2/3 below): the original discovery pass called
them dead; the phase-4 verifier proved they are imported at module level and deleting
them breaks the build. Every deletion below carries the corrected label. Where a
deletion requires unwinding an importer or migrating a test FIRST, that is stated as a
sequencing step, not a footnote.

**General citation for the corrected-label warning:** `findings.md` CF-2/CC-2 header
note ("v3 note... a handful of DISPOSITION cells carried skewed judgments and are
corrected inline") and `verification.md` Phase 4 section: "**F20: two rows
REJECTED** — `curves/modifiers.py` and `providers/native.py` ARE imported (deleting
breaks the build); re-label 'unreachable at runtime'. All other inventory rows exact."

---

### Deletion inventory (execute in this order — each numbered step is a sequencing
gate for what follows in its group; groups are otherwise independent and may be done
in any order relative to each other)

**Group A — FSCache test migration, then sync-adapter deletion (STRICT ORDER —
this is the plan's named sequencing constraint)**

> **Sequencing constraint, copied verbatim from `changes/twinklr-reactivation-review/build/plan/00-overview.md`:**
> "FSCache tests migrate **before** the sync-adapter deletion (Phase 4 debt task)."

1. **Migrate first.** `TestFSCacheSyncBackwardCompat` in
   `tests/unit/io/test_sync_adapter.py:18-19,280+` is currently the project's ONLY
   real coverage of `FSCache` store/load round trips (P1-F29,
   `foundation-and-orchestration.md:318-324`: "`FSCache` IS covered end-to-end... but
   coverage lives in the wrong package under a slated-for-deletion class and omits
   every failure mode"). Move the store/load-round-trip assertions this test makes
   into `tests/unit/caching/` **against the async `FSCache` API directly** (not
   through the sync wrapper being deleted) before touching step 2. If the migrated
   test can only exercise `FSCache` through `FSCacheSync`, that is a sign the
   migration isn't done — the async API must be exercised directly.
2. **Then delete the sync-adapter layer** (P1-F31,
   `foundation-and-orchestration.md:539-546,1306-1321`): `SyncAdapter`
   (`io/sync_adapter.py:12-65`) and its three derivatives — `FSCacheSync`
   (`caching/backends/fs.py:236-259`), `RealFileSystemSync` (`impl_real.py:138-149`),
   `NullFileSystemSync` (`impl_null.py:71`). Zero production consumers; "only
   `tests/unit/io/` uses them." Each wrapped call runs `asyncio.run()`
   (`sync_adapter.py:62`) so cannot be called from inside a running event loop
   regardless. `twinklr.core.io.sync_adapter` is one of four modules the root mypy
   config marks for strict typing — removing it also removes that carve-out; confirm
   the mypy config no longer references the deleted module.
3. **Bonus item, same evidence paragraph, unused with zero callers:** `CacheOptions`
   (`caching/models.py:58-71`) — "defined and exported (`caching/__init__.py:19,28`)
   and used nowhere." Delete alongside step 2; same file family, same verification
   pass.

**Group B — curves/modifiers.py and curves/providers/native.py: UNWIRE THEN DELETE
(the corrected-label items — do not delete these as a simple `rm`)**

> **Sequencing constraint, copied verbatim from the plan:** "unwire-then-delete the
> two 'unreachable at runtime but imported' curve rows (modifiers, providers/native —
> deleting without unwiring breaks the build)."

4. `curves/modifiers.py` (44 LOC) is **imported at module level by
   `curves/registry.py:10`**, so a direct delete breaks the build
   (`moving-heads-rendering.md:1246,1265`: "**[V] NOT deletable as-is**"). It is
   unreachable *at runtime* only because `CurveDefinition.modifiers` is never set in
   production. Sequence: (a) remove the import at `curves/registry.py:10` and any
   code path that reads `CurveDefinition.modifiers`, (b) confirm nothing else
   imports `curves/modifiers.py`, (c) delete the file.
5. `curves/providers/native.py` + `generate_native_spec`/`tune_native_spec` (116+
   LOC) is **imported by `curves/generator.py:11`**, "instantiated but never
   exercised" (`moving-heads-rendering.md:1266`). Sequence: (a) remove the import and
   instantiation at `curves/generator.py:11`, (b) confirm nothing else imports
   `curves/providers/native.py`, (c) delete the file/module.

**Group C — orphaned audio modules (phase-2 evidence; diarization excluded, goes in
P4-T1)**

6. **Genre classifier + stale context builders** (P2-F4,
   `deterministic-audio-analysis.md:655`): `genre/classifier.py`, `context/hints.py`,
   `context/unified_map.py` — "orphaned and read a pre-refactor features schema; one
   path (`vocals.statistics`) would raise `AttributeError` if executed against
   current data." Evidence: `context/hints.py:48,70,75,80-81,84,93` and
   `context/unified_map.py:193-194` vs `analyzer.py:670-693` (current schema, keys
   moved/renamed); "repo-wide grep confirms zero live importers." Delete all three
   files and their dedicated tests.
7. **The phantom-schema conftest fixture** (same finding, extended at Stage 7,
   `deterministic-audio-analysis.md:328,602`): `tests/unit/audio/conftest.py:219-`'s
   shared `sample_song_features` fixture "perpetuates the same phantom schema" that
   item 6's modules read. This fixture is shared infrastructure — before deleting
   it, grep every test file that uses `sample_song_features` and confirm none of
   them depend on the phantom (pre-refactor) shape for reasons unrelated to item 6.
   If other tests use it validly against the CURRENT schema, correct the fixture to
   match `analyzer.py`'s current schema (per P2-F4's disposition note) rather than
   deleting it outright — re-verify this against the current tree; the finding
   flags this as a REMOVE-or-fix-schema decision, not an unconditional delete.
8. **Dead `Section`/`SectionDiagnostics` model** (P2-F8,
   `deterministic-audio-analysis.md:604,660`): `structure/models.py::Section` and
   `SectionDiagnostics`. "Pydantic validators never execute against production
   data — sections/diagnostics are built as plain dicts everywhere, **and the model
   has since diverged from production dict shape** (extra fields, invalid label
   values under current constraints)." Disposition is MODERNIZE-or-REMOVE, not a
   mechanical delete — the finding explicitly revises this from FIX to "reconcile
   the model's schema with actual production output before wiring it in; not a
   mechanical one-line swap." For this task (safe deletions only), **delete the
   model** rather than attempt reconciliation — reconciling a diverged schema is
   design work, out of scope for a "safe" retirement wave. Confirm zero production
   `Section(...)`/`SectionDiagnostics(...)` constructor calls before deleting
   (repo-wide grep, per the finding's own verification method).
9. **Dead tempo-changes twin — INCLUDING its public re-export** (P2-F6,
   `deterministic-audio-analysis.md:657`, this is the item the task instructions
   specifically flag as high-stakes): `rhythm/beats.py::detect_tempo_changes` is
   dead-in-production and behaviorally diverged from the live `tempo.py` version
   (`beats.py:194-282` vs `tempo.py:11-97`). **The critical, easy-to-miss part:**
   `rhythm/__init__.py` re-exports `beats.py`'s dead copy, not `tempo.py`'s live
   one — "the dead version is the package's exported public API." Anyone doing
   `from twinklr.core.audio.rhythm import detect_tempo_changes` gets the dead,
   behaviorally-diverged function today. Deleting `beats.py::detect_tempo_changes`
   without fixing `rhythm/__init__.py`'s re-export leaves the package's public API
   broken (ImportError) or, worse if the re-export line is merely left stale,
   silently unresolvable. **Do both in the same commit**: delete
   `beats.py::detect_tempo_changes` and its dedicated tests (`test_beats.py:402-560`),
   AND repoint `rhythm/__init__.py`'s re-export to `tempo.py`'s
   `detect_tempo_changes` (the live, correct version) so the public API keeps
   working and now serves the correct implementation.

**Group D — display compat converters (two distinct `compat.py` files — do not
conflate them)**

10. **`models/compat.py` + `models/display.py`** (P5-F10,
    `display-rendering-and-xlights-io.md:678-707`): `ChoreographyGraph`
    (`templates/group/models/choreography.py`) is what all 18 non-test production
    consumers use. `DisplayGraph` (`models/display.py`, 419 lines) has zero
    production instantiations outside its own module and the converter.
    `models/compat.py`'s `choreo_graph_from_display_graph` (`:21-56`) and
    `xlights_mapping_from_display_graph` "have zero production callers" — appear
    only in `tests/unit/sequencer/templates/group/test_compat.py`. Delete
    `display.py` + `compat.py`; remove the three re-export sites:
    `templates/group/models/__init__.py:8` (docstring), `:28` (import), `:76-77`
    (the "legacy — being replaced by ChoreographyGraph" comment + `__all__` entry),
    plus `agents/sequencer/group_planner/__init__.py:67,100`; fix the stale comment
    in `engine.py:442` ("from the DisplayGraph" while actually operating on
    `self._choreo_graph`); retire the 3 associated test files. **Before deleting**:
    confirm `DisplayGraph`'s hierarchy support (`parent_group_id` with cycle
    validation) is genuinely unwanted — this is the one capability not carried
    forward into `ChoreographyGraph`; the finding flags it as "confirm... before
    deleting," not a rubber stamp.
11. **`formats/xlights/sequence/compat.py`** (a DIFFERENT file, P5-F16,
    `display-rendering-and-xlights-io.md:854-857`): `effect_placement_to_effect`
    (`:7`) has zero callers repo-wide; `xsq_export.py:88-96` reimplements the same
    conversion inline already. Delete this `compat.py` (keep the inline
    implementation in `xsq_export.py` — do not consolidate onto the dead helper).

**Group E — `SequenceAnalyzer` dead chain (extends item 11, same finding family)**

12. (P5-M5, `display-rendering-and-xlights-io.md:947-956`) `sequencer/analyzer.py::
    SequenceAnalyzer` has no callers anywhere including tests. This makes
    `xsq.py::iter_effect_placements` (`:334-356`) and `effect_type_histogram`
    (`:358-367`) unreachable in production — they are `SequenceAnalyzer`'s only
    consumers of `EffectPlacement` outside the export loop. **Delete
    `SequenceAnalyzer`, `formats/xlights/sequence/compat.py` (item 11 — sequence
    together, same finding), and the two `xsq.py` methods together** — this removes
    the entire `EffectPlacement` read-back surface as one unit, "leaving it a pure
    export-loop dataclass." Do not delete `SequenceAnalyzer` in isolation from items
    11's `compat.py`; the finding treats them as one removal.

**Group F — `simplify_rdp`**

13. (`moving-heads-rendering.md:406`) `curves/simplification.py:65`'s
    `simplify_rdp`; sole importer is `tests/unit/curves/test_simplification.py:8`.
    Delete the function and its dedicated test. Note: `curves/simplification.py` as
    a whole file also appears in the P4-F20 inventory below (item 14) — if the
    whole file's only content is `simplify_rdp` plus this test's other assertions,
    deleting the function may leave the file empty; check before deciding
    function-level vs. file-level deletion.

**Group G — the phase-4 dead-code inventory (P4-F20, corrected)** — everything below
except the two rejected rows (already excluded; see Group B) is confirmed exact by
the phase-4 verifier: "Every other inventory row was confirmed exact by the
verifier" (`moving-heads-rendering.md:1246-1250`).

14. Full table, from `moving-heads-rendering.md:1258-1275` (LOC figures are the
    phase author's AST-based counts at baseline `aa8d325` — re-verify against
    current tree before deleting, per the plan's verification-currency note):

    | Item | Path | LOC | Zero-callers evidence |
    |---|---|---|---|
    | `PoseResolver` (whole file) | `core/resolvers/poses.py` | 242 | P4-F19 — safe delete |
    | Categorical resolver (whole package) | `core/sequencer/rendering/` | 218 | P4-F18 — safe delete |
    | `ChannelState` | `moving_heads/channels/state.py:215-357` | 143 | P4-F16 ext. 2 — safe delete |
    | `curves/adapters.py` | | 332 | safe delete; also removes a layering inversion |
    | `curves/taxonomy.py` | | 151 | **no importer at all, not even a test** — safe delete |
    | `curves/protocols.py` | | 127 | **no importer at all** — safe delete |
    | `curves/simplification.py` | | 128 | see Group F above — coordinate, don't double-delete |
    | `curves/composition.py` | | 89 | safe delete |
    | `curves/dmx_conversion.py:8 movement_curve_to_dmx` | | ~30 | P4-F9 — dead conversion helper |
    | `PhaseOffsetResult.get_normalized`, `calculate_normalized_offset` | `compile/phase_offset.py:33,128` | ~25 | zero callers incl. tests |
    | `Movement.get_categorical_params` → `CURVE_INTENSITY_PARAMS` + `get_curve_categorical_params` | `models/template.py:193`, `libraries/movement.py:72,178` | ~130 | tests exist (`test_curve_intensity_params.py`) but no prod caller — delete the test with it |
    | `Intensity.amplitude` | `models/enum.py:132` | 15 | zero callers |
    | `vocabulary/intensity.py` `INTENSITY_MAP` + `resolve_intensity` | | ~20 | zero callers |
    | `TransitionDetector.detect_step_boundaries` / `detect_cycle_boundaries` | `compile/transition_detector.py:88,148` | 80 | latter is a TODO stub, never implemented |

    **CONDITIONAL — do NOT delete without re-verification:** `Colour/gobo/shutter
    libraries` (`moving_heads/libraries/{color,gobo,shutter}.py`, 643 LOC) appear in
    the same P4-F20 inventory (P4-F16) but the phase-4 deletion-order section is
    explicit: **"retaining the colour/gobo/shutter libraries if Stage 8 selects
    Stage 2 option (c)"** (`moving-heads-rendering.md:1618`). By the time this task
    runs, Phase 2P's exit criterion was "widened channel live" — **check whether
    Phase 2P's color-widening work already consumes these libraries** before
    touching them. If Phase 2P wired them in, they are no longer dead and this row
    is void. If Phase 2P deliberately did not use them (widening implemented
    differently), confirm with the current codebase/changes-tree record of that
    decision before deleting — this is exactly the kind of row where acting on a
    stale label does damage.

## Current behavior

Every item above exists in the tree, unreferenced (or referenced only by tests /
their own dead-code family) per the citations. `curves/modifiers.py` and
`curves/providers/native.py` are additionally still imported by live modules
(`curves/registry.py:10`, `curves/generator.py:11`) despite being functionally
unreachable.

## Target behavior

All items deleted per the ordering above; the build and full test suite remain green
throughout (each group's sequencing exists precisely so no intermediate state
breaks). `rhythm/__init__.py`'s public re-export resolves to the correct, live
`detect_tempo_changes` implementation. `FSCache`'s only real test coverage lives in
`tests/unit/caching/` against the async API directly, not through a wrapper that no
longer exists.

**Non-goals:** the colour/gobo/shutter libraries decision (flagged CONDITIONAL
above) is out of scope to resolve here if it requires a product decision — if
uncertain after re-verification, leave those three files untouched and flag the
uncertainty in the handoff rather than guessing. `structure/models.py::Section`
reconciliation (as opposed to deletion) is out of scope — this is a safe-deletion
wave, not a schema-modernization task.

## Implementation approach

Execute Group A → B → C → D → E → F → G in the order given (A and B have hard
internal sequencing; C through G are independent of each other and of A/B, but doing
A/B first de-risks the rest since they're the ones with real breakage potential).
After each group, run the full test suite before proceeding to the next — this
task's value is in doing many small, verifiable deletions, not one giant diff that's
hard to bisect if something breaks.

Re-verify every file/line citation against the current tree before editing — baseline
`aa8d325`; Phases 1P and 3 have merged since, so paths and line numbers may have
shifted even though the modules themselves are confirmed still dead.

## Acceptance criteria

- Every file/symbol listed above (except the CONDITIONAL colour/gobo/shutter row, if
  deferred) is deleted, along with its dedicated dead-only tests.
- `rhythm/__init__.py` exports the live `tempo.py::detect_tempo_changes`, and
  `from twinklr.core.audio.rhythm import detect_tempo_changes` returns the correct
  (previously-live) implementation, not the deleted one.
- `TestFSCacheSyncBackwardCompat`'s store/load-round-trip coverage exists in
  `tests/unit/caching/` against the async `FSCache` API, committed BEFORE the
  sync-adapter deletion commit (verifiable via `git log` order or a single PR with
  migration-then-deletion as separate commits).
- `curves/registry.py` and `curves/generator.py` no longer import the deleted
  `modifiers.py`/`providers/native.py` modules, and the build succeeds.
- `make validate` passes with zero new failures relative to the pre-task baseline
  (`memories/learnings/known-test-failures.md`).
- No `git grep` hits for any deleted symbol name outside `changes/`/`memories/`
  historical documents.

## Tests

- No new feature tests — this is deletion work. The obligation is **not regressing**
  existing coverage: any test that exercised a deleted module's *reachable* behavior
  (as opposed to testing the dead code itself) must be checked for whether it was
  actually testing something else that happens to route through the deleted
  code — if so, that test needs a replacement exercising the surviving path, not a
  deletion. Group A's FSCache migration is the one place new-test-shape work is
  required (move + adapt, not delete).

## Verification commands

```bash
uv run pytest tests/ -v
uv run mypy .
uv run ruff check .
git grep -in "detect_tempo_changes\|SequenceAnalyzer\|DisplayGraph\|SyncAdapter\|FSCacheSync\|simplify_rdp\|generate_native_spec\|CurveDefinition.modifiers" -- ':!changes' ':!memories'
```
Run this grep after each group to confirm no dangling references before moving to
the next group.

## Effort & risk

**L.** Main risk: Group B's unwind-then-delete steps are exactly where the prior
review's wrong labels would have caused breakage if followed naively — mitigated by
this spec stating the corrected sequencing explicitly. Secondary risk: the
CONDITIONAL colour/gobo/shutter row — deleting it wrongly would either break Phase
2P's widened-channel work (if it turned out to be wired) or silently foreclose a
reversible product option; mitigation is the explicit re-verification instruction
above, and defaulting to "leave it, flag it" over "guess and delete" when uncertain.

## Implementation record — 2026-08-26

Status: **frozen author candidate; pending independent verification and integration**.
Branch `codex/p4t3-dead-tail` is based on `591d1d3`. The required migration-before-
deletion ordering is explicit in commits `22fcd7e` then `8922db6`; the remaining
ordered implementation commits are `8cbd788`, `ef72fe3`, `955fab1`, `aca0936`,
`b96d10b`, and `381f47c`.

Current-tree re-verification required four narrow corrections to the baseline inventory:

- `movement_curve_to_dmx` is retained because
  `moving_heads/export/dmx_settings_builder.py` now calls it for offset-centered
  pan/tilt export.
- The color, gobo, and shutter libraries are retained because `handlers/wheels.py`,
  templates, planning models, and show coordination consume them.
- `GroupPosition` was relocated to `models/position.py` before the zero-caller legacy
  display hierarchy was deleted; its public re-export and production callers remain.
- `Intensity.amplitude`, `INTENSITY_MAP`, and `resolve_intensity` were already absent at
  the task baseline. No synthetic edit was made. Conversely, the zero-caller
  `FakeFileSystemSync` and `FileSystemSync` protocol were removed with the same
  async-only filesystem retirement after owner authorization.

Fresh author evidence after Group F/G: focused retirement regression **474 passed, 2
skipped**; touched-domain mypy **136 source files clean**; full suite **5220 passed, 38
skipped** at 88% coverage. The 42 warnings are the repository's existing SQLite
resource/deprecation warnings, not new test failures. Final `make validate`, static
deleted-symbol evidence, and the frozen candidate digest are recorded by the author
after this documentation commit; independent approval remains deliberately separate.

### Independent rejection and remediation — 2026-08-26

Independent verification **rejected** frozen snapshot `282ed6d`: the tracked
`scripts/demo_display_renderer.py` still imported `GroupPosition` from the deleted
`templates.group.models.display` module, so its `--help` path raised
`ModuleNotFoundError`. The package and test caller audit had missed tracked first-party
scripts.

Remediation commit `3c564a9` adds a subprocess smoke discriminator at
`tests/unit/scripts/test_demo_display_renderer.py` and points the demo at the surviving
`models.position.GroupPosition`. The discriminator failed before the import repair and
passes afterward. A tracked `scripts/`/`examples/` audit and a repository-wide Python
import audit find no remaining imports of any deleted display, curve, resolver, or
rendering module. The same truth pass updates the runtime macro-planner pack's stale
`DisplayGroup` comment to the surviving `ChoreoGroup` descriptor vocabulary and removes
the deleted `io.sync_adapter` strict-mypy claim from the developer guide. Because the
audited probe hashes the complete prompt pack, its offline expected prompt identity was
refreshed to `47dbc1d79c38ea2f23d5d2a5d3368aefc0be51fb142dcf9e3c707abd97b500b9`;
this does not reopen the exhausted live-attempt cap. This remediation does not expand
scope; the candidate remains pending fresh independent verification.

### Integration closeout — 2026-08-26

Fresh independent verification approved the remediation and its tracked-script/import
audit. The ordered retirement, retained live surfaces, and remediation are integrated on
main at `bf6bba5`. The historical `282ed6d` rejection remains authoritative evidence for
the stale demo import; the integrated state includes its tested repair and the associated
documentation-truth fixes.
